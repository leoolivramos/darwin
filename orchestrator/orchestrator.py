from datetime import datetime
from fastapi import FastAPI, Response, HTTPException
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from models import HotspotEvent
from state import create_cycle, get_cycle, list_cycles
from tasks import (
    process_hotspot_task, promote_cycle, rollback_cycle, reject_cycle, CycleError,
)
from utils.logger import get_logger

app = FastAPI(title="Darwin - Orchestrator", version="1.0.0")
logger = get_logger("orchestrator")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orchestrator",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/hotspot", status_code=202)
async def receive_hotspot(payload: HotspotEvent):
    """
    Ponto de entrada chamado pelo Detector quando hotspots são identificados.
    Para cada hotspot no payload, dispara um ciclo autônomo gerenciado via Celery + Redis.
    """
    logger.info(f"Evento de hotspot recebido com {len(payload.hotspots)} item(ns)")

    if not payload.hotspots:
        raise HTTPException(status_code=400, detail="Payload sem hotspots.")

    dispatched = []
    for hs in payload.hotspots:
        hs_dict = hs.model_dump()
        cycle = create_cycle(hs_dict)
        logger.info(f"Ciclo criado: id={cycle.cycle_id} | hotspot_type={hs.type}")

        # Enfileira task Celery persistente
        process_hotspot_task.delay(cycle.cycle_id, hs_dict)
        dispatched.append({"cycle_id": cycle.cycle_id, "state": cycle.state})

    return {
        "status": "accepted",
        "cycles": dispatched,
        "received_at": datetime.now().isoformat(),
    }


@app.get("/cycles")
async def get_cycles(limit: int = 20):
    """Retorna os ciclos de evolução mais recentes."""
    cycles = list_cycles(limit=limit)
    return {"total": len(cycles), "cycles": [c.model_dump() for c in cycles]}


@app.get("/cycles/{cycle_id}")
async def get_cycle_detail(cycle_id: str):
    """Retorna o estado detalhado de um ciclo específico."""
    cycle = get_cycle(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo de evolução não encontrado.")
    return cycle.model_dump()


def _decision(action, cycle_id: str, *args):
    try:
        return action(cycle_id, *args).model_dump()
    except CycleError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/cycles/{cycle_id}/approve")
async def approve_cycle(cycle_id: str):
    """Aprovação humana: promove o patch para main."""
    return _decision(promote_cycle, cycle_id)


@app.post("/cycles/{cycle_id}/reject")
async def reject_cycle_endpoint(cycle_id: str, reason: str = "Rejeitado por revisão humana"):
    return _decision(reject_cycle, cycle_id, reason)


@app.post("/cycles/{cycle_id}/rollback")
async def rollback_cycle_endpoint(cycle_id: str):
    return _decision(rollback_cycle, cycle_id)


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)
