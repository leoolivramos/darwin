from fastapi.testclient import TestClient

from metrics.scoring import evaluate_metrics


def test_regression_in_one_metric_rejects_despite_positive_score():
    baseline = {"latency_p95": 4.0, "error_rate": 0.10, "cpu_usage": 0.50}
    candidate = {"latency_p95": 1.0, "error_rate": 0.10, "cpu_usage": 0.80}  # CPU +60%
    res = evaluate_metrics(baseline, candidate)
    assert res["score"] > 10.0
    assert res["decision"] == "reject"
    assert "CPU" in res["reason"]


def test_new_errors_with_zero_baseline_are_rejected():
    baseline = {"latency_p95": 3.0, "error_rate": 0.0, "cpu_usage": 0.30}
    candidate = {"latency_p95": 1.0, "error_rate": 0.20, "cpu_usage": 0.10}
    res = evaluate_metrics(baseline, candidate)
    assert res["decision"] == "reject"
    assert "erros" in res["reason"]


def test_small_noise_does_not_block_a_good_patch():
    baseline = {"latency_p95": 3.0, "error_rate": 0.0, "cpu_usage": 0.30}
    candidate = {"latency_p95": 1.0, "error_rate": 0.0, "cpu_usage": 0.31}  # CPU +3%
    res = evaluate_metrics(baseline, candidate)
    assert res["decision"] == "approve_auto"
    assert res["reason"] is None


def test_evaluate_endpoint(load_service):
    evaluator = load_service("evaluator", "evaluator")
    client = TestClient(evaluator.app)
    body = {
        "cycle_id": "c1",
        "baseline": {"latency_p95": 2.0, "error_rate": 0.1, "cpu_usage": 0.8},
        "candidate": {"latency_p95": 1.0, "error_rate": 0.02, "cpu_usage": 0.5},
    }
    resp = client.post("/evaluate", json=body).json()
    assert resp["recommendation"] == "approve_auto"
    assert resp["cycle_id"] == "c1"
    assert resp["report"]["summary"]["decision"] == "approve_auto"
    assert client.get("/health").json()["status"] == "healthy"
