import os
import shutil
import threading
import time

import pytest
from fastapi.testclient import TestClient
from http.server import BaseHTTPRequestHandler, HTTPServer


@pytest.fixture
def sandbox(load_service):
    return load_service("sandbox-runner", "sandbox_runner")


def test_percentile_nearest_rank(sandbox):
    assert sandbox.percentile([], 95) == 0.0
    assert sandbox.percentile([1.0], 95) == 1.0
    assert sandbox.percentile(list(map(float, range(1, 101))), 95) == 95.0


def test_summarize(sandbox):
    out = sandbox.summarize([0.1, 0.2, 0.3, 0.4], errors=1, cpu_samples=[0.2, 0.4], elapsed=2.0)
    assert out["latency_p95"] == 0.4
    assert out["error_rate"] == 0.25
    assert out["cpu_usage"] == 0.3
    assert out["rps"] == 2.0
    assert sandbox.summarize([], 0, [], 0)["error_rate"] == 0.0


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/boom":
            self.send_response(500)
        else:
            self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def test_generate_load_counts_errors(sandbox):
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = sandbox.generate_load(server.server_port, ["/ok", "/boom"], duration_s=1, concurrency=2)
    finally:
        server.shutdown()
    assert result["requests"] > 0
    assert 0.3 < result["error_rate"] < 0.7  # metade das rotas falha
    assert result["latency_p95"] > 0


def test_run_lifecycle_with_validation_failure(sandbox, monkeypatch):
    def fail(*_a, **_k):
        raise sandbox.SandboxError("tests", "boom")

    monkeypatch.setattr(sandbox, "measure", fail)
    client = TestClient(sandbox.app)
    run_id = client.post("/runs", json={"candidate_ref": "darwin/x"}).json()["run_id"]
    for _ in range(50):
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] not in ("queued", "running_candidate"):
            break
        time.sleep(0.1)
    assert run["status"] == "validation_failed"
    assert run["stage"] == "tests"
    assert client.get("/runs/nope").status_code == 404


def test_run_lifecycle_completed(sandbox, monkeypatch):
    results = {"candidate": {"latency_p95": 1.0}, "baseline": {"latency_p95": 2.0}}
    monkeypatch.setattr(sandbox, "measure", lambda label, *a, **k: results[label])
    client = TestClient(sandbox.app)
    run_id = client.post("/runs", json={"candidate_ref": "darwin/x", "endpoints": ["/slow"]}).json()["run_id"]
    for _ in range(50):
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] == "completed":
            break
        time.sleep(0.1)
    assert run["status"] == "completed"
    assert run["baseline"]["latency_p95"] == 2.0
    assert run["candidate"]["latency_p95"] == 1.0
    assert run["endpoints"] == ["/slow"]
