"""
Ciclo de evolução do Darwin (tasks Celery).

    RECEIVED → GENERATING → VALIDATING → EVALUATING
        → APPROVED → DEPLOYED          (approve_auto + AUTO_PROMOTE)
        → REVIEW → DEPLOYED | REJECTED  (aprovação humana via API)
        → REJECTED | FAILED

Todas as métricas usadas na decisão vêm do Sandbox Runner (build + testes + carga
real de baseline e candidato sob as mesmas condições). Nada é estimado.
"""
import os
import time
from typing import Optional

import requests

import audit
import storage
from worker import celery_app
from state import get_cycle, update_cycle
from models import CycleState
from utils.logger import get_logger

logger = get_logger("tasks")

GENERATOR_URL  = os.getenv("GENERATOR_URL",  "http://generator:5002")
EVALUATOR_URL  = os.getenv("EVALUATOR_URL",  "http://evaluator:5001")
SANDBOX_URL    = os.getenv("SANDBOX_URL",    "http://sandbox-runner:9091")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

SANDBOX_POLL_INTERVAL = float(os.getenv("SANDBOX_POLL_INTERVAL", "5"))
SANDBOX_TIMEOUT       = int(os.getenv("SANDBOX_TIMEOUT", "1200"))
SANDBOX_DURATION      = int(os.getenv("SANDBOX_DURATION", "30"))
SANDBOX_CONCURRENCY   = int(os.getenv("SANDBOX_CONCURRENCY", "8"))
AUTO_PROMOTE          = os.getenv("AUTO_PROMOTE", "true").lower() in ("1", "true", "yes")

RECOMMENDATION_TO_STATE = {
    "approve_auto":  CycleState.APPROVED,
    "review_manual": CycleState.REVIEW,
    "reject":        CycleState.REJECTED,
}


class CycleError(Exception):
    """Falha definitiva do ciclo (sem sentido tentar de novo)."""


# ──────────────────────────────────────────────────────────────────────────────
# Passos do ciclo
# ──────────────────────────────────────────────────────────────────────────────

def _generate_patch(cycle_id: str, hotspot_data: dict) -> Optional[dict]:
    """Chama o Generator. Retorna o patch ou None se o ciclo terminou (sem regra aplicável)."""
    update_cycle(cycle_id, state=CycleState.GENERATING)
    logger.info(f"[{cycle_id}] 🧠 Gerando patch...")

    resp = requests.post(
        f"{GENERATOR_URL}/generate",
        json={"hotspots": [hotspot_data], "timestamp": time.time(), "cycle_id": cycle_id},
        timeout=120,
    )
    resp.raise_for_status()
    patch = resp.json()

    if patch.get("status") != "success":
        message = patch.get("message") or patch.get("status")
        logger.warning(f"[{cycle_id}] ⚠️ Generator: {message}")
        state = CycleState.REJECTED if patch.get("status") in ("blocked", "no_applicable_rule") else CycleState.FAILED
        update_cycle(cycle_id, state=state, error=f"Generator ({patch.get('status')}): {message}")
        return None

    update_cycle(
        cycle_id,
        patch_branch=patch.get("branch"),
        patch_commit=patch.get("commit"),
        patch_file=patch.get("file_path"),
        patch_files=patch.get("files") or [],
        patch_diff=patch.get("diff"),
        rule_applied=patch.get("rule_applied"),
        event="patch_generated",
        event_payload={"branch": patch.get("branch"), "commit": patch.get("commit"), "rule": patch.get("rule_applied")},
    )
    storage.save_patch(cycle_id, patch.get("diff") or "")
    logger.info(f"[{cycle_id}] ✅ Patch: branch={patch.get('branch')} rule={patch.get('rule_applied')}")
    return patch


def _sandbox_endpoints(hotspot_data: dict) -> list:
    endpoint = hotspot_data.get("endpoint") or ""
    return [endpoint] if endpoint.startswith("/") and "{" not in endpoint else []


def _run_sandbox(cycle_id: str, branch: str, hotspot_data: dict) -> dict:
    """Valida (build + testes) e mede baseline vs candidato. Retorna a execução concluída."""
    update_cycle(cycle_id, state=CycleState.VALIDATING)
    logger.info(f"[{cycle_id}] 🧪 Enviando {branch} ao Sandbox Runner...")

    resp = requests.post(
        f"{SANDBOX_URL}/runs",
        json={
            "cycle_id": cycle_id,
            "candidate_ref": branch,
            "baseline_ref": "main",
            "endpoints": _sandbox_endpoints(hotspot_data),
            "duration_s": SANDBOX_DURATION,
            "concurrency": SANDBOX_CONCURRENCY,
        },
        timeout=30,
    )
    resp.raise_for_status()
    run_id = resp.json()["run_id"]
    update_cycle(cycle_id, sandbox_run_id=run_id)

    deadline = time.time() + SANDBOX_TIMEOUT
    while time.time() < deadline:
        run = requests.get(f"{SANDBOX_URL}/runs/{run_id}", timeout=15)
        run.raise_for_status()
        data = run.json()
        if data["status"] in ("completed", "validation_failed", "error"):
            return data
        time.sleep(SANDBOX_POLL_INTERVAL)
    raise CycleError(f"Sandbox excedeu {SANDBOX_TIMEOUT}s (run {run_id})")


def _evaluate(cycle_id: str, baseline: dict, candidate: dict) -> dict:
    update_cycle(cycle_id, state=CycleState.EVALUATING)
    resp = requests.post(
        f"{EVALUATOR_URL}/evaluate",
        json={
            "baseline":  {k: baseline.get(k, 0.0) for k in ("latency_p95", "error_rate", "cpu_usage")},
            "candidate": {k: candidate.get(k, 0.0) for k in ("latency_p95", "error_rate", "cpu_usage")},
            "cycle_id":  cycle_id,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run_cycle(cycle_id: str, hotspot_data: dict) -> dict:
    """Executa o ciclo completo. Exceções `requests.RequestException` são transitórias."""
    patch = _generate_patch(cycle_id, hotspot_data)
    if patch is None:
        return {"cycle_id": cycle_id, "state": get_cycle(cycle_id).state.value}

    update_cycle(cycle_id, production_metrics=_collect_prometheus_metrics())

    run = _run_sandbox(cycle_id, patch["branch"], hotspot_data)

    if run["status"] == "validation_failed":
        reason = f"Patch reprovado na validação ({run.get('stage')}): {run.get('error')}"
        logger.warning(f"[{cycle_id}] ❌ {reason[:300]}")
        update_cycle(cycle_id, state=CycleState.REJECTED, recommendation="reject", error=reason[:2000],
                     event="validation_failed", event_payload={"stage": run.get("stage")})
        return {"cycle_id": cycle_id, "state": "rejected", "reason": "validation_failed"}
    if run["status"] == "error":
        raise CycleError(f"Sandbox falhou: {run.get('error')}")

    baseline, candidate = run["baseline"], run["candidate"]
    update_cycle(cycle_id, baseline_metrics=baseline, candidate_metrics=candidate,
                 event="sandbox_completed", event_payload={"baseline": baseline, "candidate": candidate})
    storage.save_report(cycle_id, "sandbox", {"run": run})
    logger.info(f"[{cycle_id}] 📊 Baseline={baseline} | Candidato={candidate}")

    evaluation = _evaluate(cycle_id, baseline, candidate)
    score          = evaluation.get("score", 0.0)
    recommendation = evaluation.get("recommendation", "reject")
    final_state    = RECOMMENDATION_TO_STATE.get(recommendation, CycleState.REJECTED)

    update_cycle(cycle_id, state=final_state, score=score, recommendation=recommendation, evaluation=evaluation,
                 event="evaluated", event_payload={"score": score, "recommendation": recommendation})
    storage.save_report(cycle_id, "evaluation", evaluation)
    logger.info(f"[{cycle_id}] 🏁 Avaliação: state={final_state.value} score={score:.2f}")

    if final_state == CycleState.APPROVED and AUTO_PROMOTE:
        promote_cycle(cycle_id)

    return {"cycle_id": cycle_id, "state": get_cycle(cycle_id).state.value, "score": score}


# ──────────────────────────────────────────────────────────────────────────────
# Deploy / rollback / decisão humana
# ──────────────────────────────────────────────────────────────────────────────

def promote_cycle(cycle_id: str):
    """Integra o branch do ciclo em `main` (deploy). Chamado automaticamente ou via aprovação humana."""
    cycle = get_cycle(cycle_id)
    if cycle is None:
        raise CycleError("Ciclo não encontrado.")
    if cycle.state not in (CycleState.APPROVED, CycleState.REVIEW):
        raise CycleError(f"Ciclo em estado '{cycle.state.value}' não pode ser promovido.")
    if not cycle.patch_branch:
        raise CycleError("Ciclo sem branch de patch.")

    resp = requests.post(
        f"{GENERATOR_URL}/promote",
        json={"branch": cycle.patch_branch, "cycle_id": cycle_id},
        timeout=60,
    )
    if resp.status_code >= 400:
        detail = resp.json().get("detail") if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        update_cycle(cycle_id, error=f"Promote falhou: {detail}", event="promote_failed", event_payload={"detail": detail})
        raise CycleError(f"Promote falhou: {detail}")

    deployment = resp.json()
    logger.info(f"[{cycle_id}] 🚀 Promovido para main: {deployment.get('commit', '')[:8]} tag={deployment.get('tag')}")
    return update_cycle(cycle_id, state=CycleState.DEPLOYED, deployment=deployment, error=None,
                        event="deployed", event_payload=deployment)


def rollback_cycle(cycle_id: str):
    """Reverte em `main` o commit promovido por este ciclo."""
    cycle = get_cycle(cycle_id)
    if cycle is None:
        raise CycleError("Ciclo não encontrado.")
    if cycle.state != CycleState.DEPLOYED or not cycle.deployment:
        raise CycleError("Apenas ciclos em 'deployed' podem sofrer rollback.")

    resp = requests.post(
        f"{GENERATOR_URL}/rollback",
        json={"commit": cycle.deployment["commit"], "cycle_id": cycle_id},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise CycleError(f"Rollback falhou: {resp.text}")

    rollback = resp.json()
    logger.info(f"[{cycle_id}] ⏪ Rollback concluído: {rollback.get('tag')}")
    return update_cycle(cycle_id, state=CycleState.ROLLED_BACK, rollback=rollback,
                        event="rolled_back", event_payload=rollback)


def reject_cycle(cycle_id: str, reason: str = "Rejeitado por revisão humana"):
    cycle = get_cycle(cycle_id)
    if cycle is None:
        raise CycleError("Ciclo não encontrado.")
    if cycle.state not in (CycleState.REVIEW, CycleState.APPROVED):
        raise CycleError(f"Ciclo em estado '{cycle.state.value}' não pode ser rejeitado.")
    return update_cycle(cycle_id, state=CycleState.REJECTED, error=reason,
                        event="rejected_by_human", event_payload={"reason": reason})


# ──────────────────────────────────────────────────────────────────────────────
# Task Celery
# ──────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="orchestrator.process_hotspot",
    max_retries=2,
    default_retry_delay=30,
)
def process_hotspot_task(self, cycle_id: str, hotspot_data: dict):
    """Executa o ciclo; só falhas de rede (transitórias) são reexecutadas."""
    try:
        return run_cycle(cycle_id, hotspot_data)
    except requests.RequestException as exc:
        if self.request.retries < self.max_retries:
            logger.warning(f"[{cycle_id}] 🔁 Falha transitória, nova tentativa: {exc}")
            raise self.retry(exc=exc)
        logger.error(f"[{cycle_id}] ❌ Falha de rede definitiva: {exc}")
        update_cycle(cycle_id, state=CycleState.FAILED, error=f"Rede: {exc}")
        return {"cycle_id": cycle_id, "state": "failed", "reason": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[{cycle_id}] ❌ Falha no ciclo: {exc}")
        update_cycle(cycle_id, state=CycleState.FAILED, error=str(exc))
        return {"cycle_id": cycle_id, "state": "failed", "reason": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# Auxiliares
# ──────────────────────────────────────────────────────────────────────────────

def _collect_prometheus_metrics() -> dict:
    """
    Snapshot informativo das métricas de produção (Prometheus). Não participa da
    decisão — serve de contexto no registro de auditoria. Zeros se indisponível.
    """
    def query(q: str) -> float:
        try:
            r = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": q}, timeout=5)
            results = r.json().get("data", {}).get("result", [])
            if results:
                return round(float(results[0]["value"][1]), 4)
        except Exception:  # noqa: BLE001
            pass
        return 0.0

    return {
        "latency_p95": query('histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket[5m])) by (le))'),
        "error_rate": query(
            'sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m])) / '
            'sum(rate(http_server_requests_seconds_count[5m]))'
        ),
        "cpu_usage": query('avg(rate(process_cpu_seconds_total[5m]))'),
    }
