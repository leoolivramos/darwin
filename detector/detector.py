from fastapi import FastAPI, BackgroundTasks
import requests
import os
import time
import redis
from typing import Optional

from models import Hotspot, HotspotEvent, HotspotType, DetectionResult

app = FastAPI(title="Darwin - Hotspot Detector", version="1.0.0")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:5003")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
DEBOUNCE_TTL = int(os.getenv("DEBOUNCE_TTL", "300"))  # 5 minutos de cooldown por hotspot

_redis_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=3)
        except Exception as e:
            print(f"⚠️ Redis indisponível para debounce: {e}")
            _redis_client = None
    return _redis_client


def read_query(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "queries", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def run_promql(query: str) -> list:
    if not query:
        return []
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=5)
        data = resp.json()
        return data.get("data", {}).get("result", [])
    except Exception as e:
        print(f"❌ Erro ao consultar Prometheus: {e}")
        return []


def _is_debounced(hotspot_key: str) -> bool:
    r = get_redis()
    if r:
        try:
            return r.exists(f"darwin:debounce:{hotspot_key}") > 0
        except Exception:
            pass
    return False


def _set_debounce(hotspot_key: str):
    r = get_redis()
    if r:
        try:
            r.setex(f"darwin:debounce:{hotspot_key}", DEBOUNCE_TTL, "1")
        except Exception:
            pass


def scan_and_notify() -> list[Hotspot]:
    print("🔍 Iniciando varredura de métricas no Prometheus...")

    latency_query = read_query("latency_query.promql") or 'histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket[5m])) by (le, uri))'
    error_query = read_query("error_query.promql") or 'sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m])) by (uri) / sum(rate(http_server_requests_seconds_count[5m])) by (uri)'
    cpu_query = read_query("cpu_usage.promql") or 'avg(rate(process_cpu_seconds_total[5m])) by (instance)'

    hotspots: list[Hotspot] = []

    # 1. Latency
    for res in run_promql(latency_query):
        try:
            endpoint = res["metric"].get("uri", "unknown")
            val = float(res["value"][1])
            threshold = float(os.getenv("DETECTOR_THRESHOLD_LATENCY", "2.0"))
            if val > threshold:
                key = f"latency:{endpoint}"
                if not _is_debounced(key):
                    hotspots.append(Hotspot(type=HotspotType.LATENCY, endpoint=endpoint, value=val, threshold=threshold))
                    _set_debounce(key)
        except (KeyError, ValueError, IndexError):
            continue

    # 2. Error Rate
    for res in run_promql(error_query):
        try:
            endpoint = res["metric"].get("uri", "unknown")
            val = float(res["value"][1])
            threshold = float(os.getenv("DETECTOR_THRESHOLD_ERROR_RATE", "0.05"))
            if val > threshold:
                key = f"error:{endpoint}"
                if not _is_debounced(key):
                    hotspots.append(Hotspot(type=HotspotType.ERROR_RATE, endpoint=endpoint, value=val, threshold=threshold))
                    _set_debounce(key)
        except (KeyError, ValueError, IndexError):
            continue

    # 3. CPU Usage
    for res in run_promql(cpu_query):
        try:
            instance = res["metric"].get("instance", "unknown")
            val = float(res["value"][1])
            threshold = float(os.getenv("DETECTOR_THRESHOLD_CPU", "0.80"))
            if val > threshold:
                key = f"cpu:{instance}"
                if not _is_debounced(key):
                    hotspots.append(Hotspot(type=HotspotType.CPU_USAGE, instance=instance, value=val, threshold=threshold))
                    _set_debounce(key)
        except (KeyError, ValueError, IndexError):
            continue

    if hotspots:
        print(f"🚨 {len(hotspots)} novo(s) hotspot(s) detectado(s) (pós-debounce)!")
        try:
            payload = HotspotEvent(hotspots=hotspots, timestamp=time.time()).model_dump()
            requests.post(f"{ORCHESTRATOR_URL}/hotspot", json=payload, timeout=5)
        except Exception as e:
            print(f"❌ Falha ao notificar Orchestrator: {e}")
    else:
        print("✅ Nenhum hotspot novo detectado nesta varredura.")

    return hotspots


def schedule_detection():
    while True:
        try:
            scan_and_notify()
        except Exception as e:
            print(f"❌ Erro no loop de detecção: {e}")
        time.sleep(CHECK_INTERVAL)


@app.on_event("startup")
def on_startup():
    print(f"🚀 Detector iniciado. Intervalo: {CHECK_INTERVAL}s | Debounce TTL: {DEBOUNCE_TTL}s")
    import threading
    t = threading.Thread(target=schedule_detection, daemon=True)
    t.start()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "detector",
        "check_interval": CHECK_INTERVAL,
        "prometheus_url": PROMETHEUS_URL,
    }


@app.post("/scan", response_model=DetectionResult)
def manual_scan(background_tasks: BackgroundTasks):
    """Executa uma varredura manual sob demanda."""
    hotspots = scan_and_notify()
    return DetectionResult(
        hotspots=hotspots,
        scan_timestamp=time.time(),
        prometheus_url=PROMETHEUS_URL,
    )
