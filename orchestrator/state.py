"""
Gerenciamento de estado dos ciclos de evolução no Redis.
Cada ciclo é armazenado como JSON com TTL de 7 dias.
O índice sorted-set `darwin:cycles` permite listar ciclos por data.
"""
import redis
import json
import os
import time
from typing import Optional
import audit
from models import CycleRecord, CycleState, HotspotData

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CYCLE_TTL = 60 * 60 * 24 * 7  # 7 dias

_redis: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
    return _redis


def _cycle_key(cycle_id: str) -> str:
    return f"darwin:cycle:{cycle_id}"


def create_cycle(hotspot: dict) -> CycleRecord:
    """Cria um novo CycleRecord no Redis e retorna o objeto criado."""
    hotspot_obj = HotspotData(**hotspot)
    cycle = CycleRecord(hotspot=hotspot_obj)
    key = _cycle_key(cycle.cycle_id)
    r = get_redis()
    r.setex(key, CYCLE_TTL, cycle.model_dump_json())
    r.zadd("darwin:cycles", {cycle.cycle_id: cycle.created_at})
    audit.sync_cycle(cycle)
    audit.record_event(cycle.cycle_id, "state:received", {"hotspot": hotspot})
    return cycle


def update_cycle(cycle_id: str, event: Optional[str] = None, event_payload: Optional[dict] = None,
                 **kwargs) -> Optional[CycleRecord]:
    """
    Atualiza campos de um CycleRecord existente e registra a mudança na auditoria.
    Mudanças de `state` geram o evento `state:<novo>`; `event` registra um evento extra.
    """
    r = get_redis()
    key = _cycle_key(cycle_id)
    data = r.get(key)
    if not data:
        return None
    cycle = CycleRecord.model_validate_json(data)
    previous_state = cycle.state
    for field, value in kwargs.items():
        if hasattr(cycle, field):
            setattr(cycle, field, value)
    cycle.updated_at = time.time()
    r.setex(key, CYCLE_TTL, cycle.model_dump_json())

    audit.sync_cycle(cycle)
    if cycle.state != previous_state:
        audit.record_event(cycle_id, f"state:{cycle.state.value}", {"from": previous_state.value, "error": cycle.error})
    if event:
        audit.record_event(cycle_id, event, event_payload)
    return cycle


def get_cycle(cycle_id: str) -> Optional[CycleRecord]:
    """Recupera um CycleRecord pelo ID. Retorna None se não encontrado."""
    data = get_redis().get(_cycle_key(cycle_id))
    return CycleRecord.model_validate_json(data) if data else None


def list_cycles(limit: int = 20) -> list[CycleRecord]:
    """Retorna os N ciclos mais recentes em ordem decrescente de criação."""
    r = get_redis()
    cycle_ids = r.zrevrange("darwin:cycles", 0, limit - 1)
    result = []
    for cid in cycle_ids:
        c = get_cycle(cid)
        if c:
            result.append(c)
    return result
