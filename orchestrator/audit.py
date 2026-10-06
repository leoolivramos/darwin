"""
Trilha de auditoria persistente dos ciclos de evolução (PostgreSQL).

O Redis guarda o estado operacional (TTL de 7 dias); o PostgreSQL guarda o
histórico permanente: tabela `cycles` (último estado), `patches`, `evaluations`
e `audit_events` (log append-only de cada transição/decisão).

Falhas de auditoria nunca derrubam o ciclo — são logadas e o fluxo segue.
"""
import json
import os
from typing import Optional

from utils.logger import get_logger

logger = get_logger("audit")

_SCHEMA_READY = False

_AUDIT_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS audit_events (
    id         BIGSERIAL PRIMARY KEY,
    cycle_id   UUID NOT NULL,
    event      VARCHAR(100) NOT NULL,
    payload    JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_events_cycle ON audit_events(cycle_id, created_at);
"""


def _enabled() -> bool:
    return os.getenv("AUDIT_ENABLED", "true").lower() in ("1", "true", "yes")


def _connect():
    import psycopg2

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "darwin"),
        user=os.getenv("POSTGRES_USER", "darwin_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=5,
    )


def _ensure_schema(cur) -> None:
    """Cria audit_events em bancos já inicializados (init.sql só roda no primeiro boot)."""
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        cur.execute(_AUDIT_EVENTS_DDL)
        _SCHEMA_READY = True


def _json(value) -> Optional[str]:
    return json.dumps(value, default=str) if value is not None else None


def sync_cycle(cycle) -> None:
    """Upsert do estado atual do ciclo (e do patch/avaliação quando existirem)."""
    if not _enabled():
        return
    hs = cycle.hotspot
    try:
        conn = _connect()
        try:
            with conn, conn.cursor() as cur:
                _ensure_schema(cur)
                cur.execute(
                    """
                    INSERT INTO cycles (cycle_id, state, hotspot_type, hotspot_endpoint, hotspot_instance,
                        hotspot_value, hotspot_threshold, patch_branch, patch_file, rule_applied,
                        baseline_metrics, candidate_metrics, score, recommendation, error)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                    ON CONFLICT (cycle_id) DO UPDATE SET
                        state=EXCLUDED.state, patch_branch=EXCLUDED.patch_branch,
                        patch_file=EXCLUDED.patch_file, rule_applied=EXCLUDED.rule_applied,
                        baseline_metrics=EXCLUDED.baseline_metrics,
                        candidate_metrics=EXCLUDED.candidate_metrics, score=EXCLUDED.score,
                        recommendation=EXCLUDED.recommendation, error=EXCLUDED.error
                    """,
                    (
                        cycle.cycle_id, cycle.state.value,
                        hs.type if hs else None, hs.endpoint if hs else None, hs.instance if hs else None,
                        hs.value if hs else None, hs.threshold if hs else None,
                        cycle.patch_branch, cycle.patch_file, cycle.rule_applied,
                        _json(cycle.baseline_metrics), _json(cycle.candidate_metrics),
                        cycle.score, cycle.recommendation, cycle.error,
                    ),
                )
                if cycle.patch_branch:
                    cur.execute(
                        """
                        INSERT INTO patches (cycle_id, branch_name, file_path, rule_applied, diff)
                        SELECT %s,%s,%s,%s,%s
                        WHERE NOT EXISTS (SELECT 1 FROM patches WHERE cycle_id=%s AND branch_name=%s)
                        """,
                        (cycle.cycle_id, cycle.patch_branch, cycle.patch_file, cycle.rule_applied,
                         cycle.patch_diff, cycle.cycle_id, cycle.patch_branch),
                    )
                if cycle.evaluation:
                    details = cycle.evaluation
                    cur.execute(
                        """
                        INSERT INTO evaluations (cycle_id, score, recommendation, confidence,
                            delta_latency_pct, delta_error_pct, delta_cpu_pct,
                            baseline_metrics, candidate_metrics, report)
                        SELECT %s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb
                        WHERE NOT EXISTS (SELECT 1 FROM evaluations WHERE cycle_id=%s)
                        """,
                        (cycle.cycle_id, details.get("score", 0.0), details.get("recommendation", "reject"),
                         details.get("confidence"), details.get("delta_latency_pct"),
                         details.get("delta_error_pct"), details.get("delta_cpu_pct"),
                         _json(cycle.baseline_metrics), _json(cycle.candidate_metrics),
                         _json(details.get("report")), cycle.cycle_id),
                    )
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ Auditoria (cycles) indisponível: {e}")


def record_event(cycle_id: str, event: str, payload: Optional[dict] = None) -> None:
    """Registra um evento append-only (transição de estado, deploy, rollback, ...)."""
    if not _enabled():
        return
    try:
        conn = _connect()
        try:
            with conn, conn.cursor() as cur:
                _ensure_schema(cur)
                cur.execute(
                    "INSERT INTO audit_events (cycle_id, event, payload) VALUES (%s,%s,%s::jsonb)",
                    (cycle_id, event, _json(payload)),
                )
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ Auditoria (evento {event}) indisponível: {e}")
