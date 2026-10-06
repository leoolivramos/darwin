"""Smoke test de integração: sobe a stack (docker compose) e valida o fluxo básico.

Uso: python tests/integration/smoke_test.py
"""
import sys
import time
import urllib.request
import json

SERVICES = {
    "orchestrator": "http://localhost:5003/health",
    "generator": "http://localhost:5002/health",
    "evaluator": "http://localhost:5001/health",
    "detector": "http://localhost:5004/health",
    "sandbox-runner": "http://localhost:9091/health",
    "prometheus": "http://localhost:9090/-/healthy",
}


def http(url, data=None, timeout=10):
    req = urllib.request.Request(url, method="POST" if data is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(data).encode()
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        return r.status, r.read().decode()


def wait_healthy(name, url, deadline=180):
    end = time.time() + deadline
    while time.time() < end:
        try:
            if http(url)[0] == 200:
                print(f"[ok] {name}")
                return
        except Exception:
            time.sleep(3)
    sys.exit(f"[falha] {name} não ficou saudável em {deadline}s")


def main():
    for name, url in SERVICES.items():
        wait_healthy(name, url)

    payload = {"hotspots": [{
        "type": "latency", "endpoint": "/slow", "instance": "app:8080",
        "value": 2.5, "threshold": 0.5,
    }]}
    status, body = http("http://localhost:5003/hotspot", payload)
    if status != 202:
        sys.exit(f"[falha] /hotspot retornou {status}: {body}")
    cycle_id = json.loads(body)["cycles"][0]["cycle_id"]
    print(f"[ok] ciclo criado: {cycle_id}")

    status, body = http(f"http://localhost:5003/cycles/{cycle_id}")
    if status != 200:
        sys.exit(f"[falha] ciclo {cycle_id} não consultável")
    print("[ok] smoke test concluído")


if __name__ == "__main__":
    main()
