from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import uuid
import time


class CycleState(str, Enum):
    """Estados possíveis de um ciclo de evolução (FSM).

    received → generating → validating (sandbox: build + testes + carga) → evaluating
      → approved → deployed → (rolled_back)
      → review (aguarda aprovação humana) → deployed | rejected
      → rejected | failed
    """
    RECEIVED           = "received"
    GENERATING         = "generating"
    VALIDATING         = "validating"
    EVALUATING         = "evaluating"
    APPROVED           = "approved"
    DEPLOYED           = "deployed"
    ROLLED_BACK        = "rolled_back"
    REJECTED           = "rejected"
    REVIEW             = "review"
    FAILED             = "failed"


class HotspotData(BaseModel):
    """Representação de um hotspot dentro do Orchestrator."""
    type: str
    endpoint: Optional[str] = None
    instance: Optional[str] = None
    value: float
    threshold: float
    timestamp: Optional[float] = None


class HotspotEvent(BaseModel):
    """Payload recebido do Detector."""
    hotspots: list[HotspotData]
    timestamp: float = Field(default_factory=time.time)


class CycleRecord(BaseModel):
    """Registro completo de um ciclo de evolução, persistido no Redis."""
    cycle_id:          str        = Field(default_factory=lambda: str(uuid.uuid4()))
    state:             CycleState = CycleState.RECEIVED
    hotspot:           Optional[HotspotData] = None

    # Geração
    patch_branch:  Optional[str] = None
    patch_commit:  Optional[str] = None
    patch_file:    Optional[str] = None
    patch_files:   list[str] = Field(default_factory=list)
    patch_diff:    Optional[str] = None
    rule_applied:  Optional[str] = None

    # Sandbox / avaliação
    sandbox_run_id:     Optional[str]  = None
    production_metrics: Optional[dict] = None   # snapshot do Prometheus (informativo)
    baseline_metrics:   Optional[dict] = None   # medido no sandbox
    candidate_metrics:  Optional[dict] = None   # medido no sandbox
    score:              Optional[float] = None
    recommendation:     Optional[str]  = None
    evaluation:         Optional[dict] = None

    # Deploy (promote em main) e rollback
    deployment: Optional[dict] = None
    rollback:   Optional[dict] = None

    # Diagnóstico
    error: Optional[str] = None

    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
