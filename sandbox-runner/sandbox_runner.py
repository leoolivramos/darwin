"""
Darwin Sandbox Runner
=====================
Valida e mede um branch candidato em ambiente isolado e reproduzível:

  1. Extrai `baseline_ref` e `candidate_ref` do repositório git (somente leitura).
  2. Compila (candidato: `mvn package` com testes = validação do patch).
  3. Sobe cada versão numa JVM própria, sob a MESMA carga sintética.
  4. Mede latência p95, taxa de erro e CPU reais de cada versão.

As métricas devolvidas substituem a antiga estimativa por fatores fixos.
"""
import glob
import io
import math
import os
import shutil
import subprocess
import tarfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field

REPO_PATH = os.getenv("REPO_PATH", "/repo")
WORK_DIR = os.getenv("SANDBOX_WORK_DIR", "/work")
APP_PORT = int(os.getenv("SANDBOX_APP_PORT", "18080"))
DEFAULT_ENDPOINTS = [e.strip() for e in os.getenv("SANDBOX_DEFAULT_ENDPOINTS", "/hello,/slow").split(",") if e.strip()]
BUILD_TIMEOUT = int(os.getenv("SANDBOX_BUILD_TIMEOUT", "600"))
STARTUP_TIMEOUT = int(os.getenv("SANDBOX_STARTUP_TIMEOUT", "120"))
JAVA_OPTS = os.getenv("SANDBOX_JAVA_OPTS", "-Xmx512m").split()

app = FastAPI(title="Darwin - Sandbox Runner", version="1.0.0")

RUNS_TOTAL = Counter("sandbox_runs_total", "Execuções do sandbox por resultado", ["result"])

_runs: dict = {}
_runs_lock = threading.Lock()
_exec_lock = threading.Lock()  # uma execução por vez: portas e CPU são compartilhados


class RunRequest(BaseModel):
    cycle_id: Optional[str] = None
    candidate_ref: str
    baseline_ref: str = "main"
    endpoints: list[str] = Field(default_factory=list)
    duration_s: int = Field(default=30, ge=1, le=600)
    warmup_s: int = Field(default=5, ge=0, le=120)
    concurrency: int = Field(default=8, ge=1, le=64)


class SandboxError(Exception):
    """Falha de build, teste ou inicialização de uma versão."""

    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


# ── estatística ──────────────────────────────────────────────────────────────
def percentile(values: list, pct: float) -> float:
    """Percentil por método nearest-rank. Lista vazia → 0.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[rank - 1]


def summarize(latencies: list, errors: int, cpu_samples: list, elapsed: float) -> dict:
    total = len(latencies)
    return {
        "latency_p95": round(percentile(latencies, 95), 4),
        "error_rate": round(errors / total, 4) if total else 0.0,
        "cpu_usage": round(sum(cpu_samples) / len(cpu_samples), 4) if cpu_samples else 0.0,
        "requests": total,
        "rps": round(total / elapsed, 2) if elapsed > 0 else 0.0,
    }


# ── build & execução ─────────────────────────────────────────────────────────
def _run(cmd: list, cwd: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace", timeout=timeout)


def extract_ref(ref: str, dest: str) -> None:
    """Extrai o conteúdo de `ref` do repositório git para `dest` (sem tocar no repo)."""
    proc = subprocess.run(
        ["git", "-C", REPO_PATH, "archive", "--format=tar", ref],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SandboxError("checkout", f"git archive {ref} falhou: {proc.stderr.decode(errors='replace')[-500:]}")
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
        tar.extractall(dest, filter="data")


def build(workdir: str, run_tests: bool) -> None:
    cmd = ["mvn", "-B", "-q", "package"] + ([] if run_tests else ["-DskipTests"])
    stage = "tests" if run_tests else "build"
    try:
        proc = _run(cmd, workdir, BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SandboxError(stage, f"mvn excedeu {BUILD_TIMEOUT}s")
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-1500:]
        raise SandboxError(stage, f"mvn {' '.join(cmd[3:])} falhou:\n{tail}")


def find_jar(workdir: str) -> str:
    jars = [j for j in glob.glob(os.path.join(workdir, "target", "*.jar")) if not j.endswith(".original")]
    if not jars:
        raise SandboxError("build", "Nenhum .jar gerado em target/")
    return jars[0]


def start_app(jar: str, port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        ["java", *JAVA_OPTS, "-jar", jar, f"--server.port={port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
    )
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read()[-1500:] if proc.stdout else ""
            raise SandboxError("startup", f"Aplicação encerrou ao iniciar:\n{out}")
        try:
            if requests.get(f"http://localhost:{port}/actuator/health", timeout=2).status_code == 200:
                return proc
        except requests.RequestException:
            pass
        time.sleep(1)
    stop_app(proc)
    raise SandboxError("startup", f"Aplicação não ficou saudável em {STARTUP_TIMEOUT}s")


def stop_app(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    if proc.stdout:
        proc.stdout.close()


def _cpu_sampler(port: int, stop: threading.Event, samples: list) -> None:
    url = f"http://localhost:{port}/actuator/metrics/process.cpu.usage"
    while not stop.is_set():
        try:
            value = requests.get(url, timeout=2).json()["measurements"][0]["value"]
            samples.append(float(value))
        except Exception:
            pass
        stop.wait(1.0)


def generate_load(port: int, endpoints: list, duration_s: int, concurrency: int) -> dict:
    """Carga fechada: `concurrency` clientes percorrendo `endpoints` por `duration_s` segundos."""
    latencies, errors, lock = [], [0], threading.Lock()
    deadline = time.time() + duration_s

    def worker(idx: int):
        session = requests.Session()
        n = idx
        while time.time() < deadline:
            path = endpoints[n % len(endpoints)]
            n += 1
            started = time.perf_counter()
            failed = False
            try:
                failed = session.get(f"http://localhost:{port}{path}", timeout=30).status_code >= 500
            except requests.RequestException:
                failed = True
            elapsed = time.perf_counter() - started
            with lock:
                latencies.append(elapsed)
                if failed:
                    errors[0] += 1

    cpu_samples: list = []
    stop = threading.Event()
    sampler = threading.Thread(target=_cpu_sampler, args=(port, stop, cpu_samples), daemon=True)
    sampler.start()
    started = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for i in range(concurrency):
            pool.submit(worker, i)
    elapsed = time.time() - started
    stop.set()
    sampler.join(timeout=3)
    return summarize(latencies, errors[0], cpu_samples, elapsed)


def measure(label: str, ref: str, run_dir: str, req: RunRequest, endpoints: list, run_tests: bool) -> dict:
    workdir = os.path.join(run_dir, label)
    extract_ref(ref, workdir)
    build(workdir, run_tests=run_tests)
    jar = find_jar(workdir)

    proc = start_app(jar, APP_PORT)
    try:
        if req.warmup_s:
            generate_load(APP_PORT, endpoints, req.warmup_s, req.concurrency)
        return generate_load(APP_PORT, endpoints, req.duration_s, req.concurrency)
    finally:
        stop_app(proc)


# ── orquestração de uma execução ─────────────────────────────────────────────
def _update(run_id: str, **fields) -> None:
    with _runs_lock:
        _runs[run_id].update(fields, updated_at=time.time())


def execute_run(run_id: str, req: RunRequest) -> None:
    run_dir = os.path.join(WORK_DIR, run_id)
    endpoints = req.endpoints or DEFAULT_ENDPOINTS
    with _exec_lock:
        try:
            _update(run_id, endpoints=endpoints)

            # O candidato é construído COM testes: é a validação do patch.
            _update(run_id, status="running_candidate")
            candidate = measure("candidate", req.candidate_ref, run_dir, req, endpoints, run_tests=True)

            _update(run_id, status="running_baseline", candidate=candidate)
            baseline = measure("baseline", req.baseline_ref, run_dir, req, endpoints, run_tests=False)

            _update(run_id, status="completed", baseline=baseline, candidate=candidate)
            RUNS_TOTAL.labels("completed").inc()
        except SandboxError as e:
            _update(run_id, status="validation_failed", stage=e.stage, error=e.message)
            RUNS_TOTAL.labels("validation_failed").inc()
        except Exception as e:  # noqa: BLE001
            _update(run_id, status="error", error=str(e))
            RUNS_TOTAL.labels("error").inc()
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "sandbox-runner", "timestamp": datetime.now().isoformat()}


@app.post("/runs", status_code=202)
def create_run(req: RunRequest):
    """Agenda a validação + medição de um branch candidato. Consulte `GET /runs/{id}`."""
    run_id = uuid.uuid4().hex[:12]
    with _runs_lock:
        _runs[run_id] = {
            "run_id": run_id, "cycle_id": req.cycle_id, "status": "queued",
            "candidate_ref": req.candidate_ref, "baseline_ref": req.baseline_ref,
            "created_at": time.time(), "updated_at": time.time(),
        }
    threading.Thread(target=execute_run, args=(run_id, req), daemon=True).start()
    return {"run_id": run_id, "status": "queued"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    with _runs_lock:
        run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return run


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9091)
