import os
from datetime import datetime
from fastapi import FastAPI, Response, HTTPException
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from models import (
    GenerationRequest, PatchResult, HotspotType, PromoteRequest, RollbackRequest,
)
from utils.git_helper import GitHelper, GitError, NoChanges
from utils.ast_parser import ASTParser
from utils.guard import find_protected
from utils.logger import get_logger

from heuristics.base import RuleNotApplicable
from heuristics.timeout_rule import plan_timeout
from heuristics.pool_size_rule import plan_pool_size
from heuristics.caching_rule import plan_caching

app = FastAPI(title="Darwin - Patch Generator", version="1.1.0")
logger = get_logger("generator")

REPO_PATH = os.getenv("REPO_PATH", "/repo")
git = GitHelper(repo_path=REPO_PATH)
parser = ASTParser(repo_path=REPO_PATH)

RULES = {
    "caching": plan_caching,
    "timeout": plan_timeout,
    "pool_size": plan_pool_size,
}

# Ordem de tentativa por tipo de hotspot: usa a primeira regra aplicável.
RULES_BY_HOTSPOT = {
    HotspotType.LATENCY: ["caching", "timeout", "pool_size"],
    HotspotType.CPU_USAGE: ["pool_size", "caching"],
    HotspotType.ERROR_RATE: ["timeout"],
}


def rules_for_hotspot(hotspot_type: HotspotType) -> list:
    """Regras candidatas (em ordem de prioridade) para o tipo de hotspot."""
    return RULES_BY_HOTSPOT.get(hotspot_type, ["timeout"])


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "generator",
        "repo_path": REPO_PATH,
        "repo_ready": git.has_commits(),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/generate", response_model=PatchResult)
def generate_patch(payload: GenerationRequest):
    """
    Gera um patch real para o hotspot recebido:
      1. Localiza o arquivo Java que atende o endpoint.
      2. Tenta as heurísticas aplicáveis ao tipo de hotspot.
      3. Bloqueia mudanças em módulos críticos (revisão humana).
      4. Cria um branch git `darwin/*` com o commit do patch.
    """
    logger.info(f"🧠 Solicitação de geração recebida: {len(payload.hotspots)} hotspot(s)")

    if not payload.hotspots:
        raise HTTPException(status_code=400, detail="Nenhum hotspot fornecido no payload.")
    if not git.has_commits():
        raise HTTPException(status_code=503, detail="Repositório de código vazio (APP_SOURCE_PATH não semeado).")

    hotspot = payload.hotspots[0]
    hotspot_dict = hotspot.model_dump(mode="json")

    file_path = parser.find_relevant_file(hotspot_dict)
    if not file_path:
        return PatchResult(status="no_applicable_rule", message="Nenhum arquivo Java relevante encontrado no repositório.")

    reasons = []
    for rule_name in rules_for_hotspot(hotspot.type):
        try:
            changes = RULES[rule_name](REPO_PATH, file_path, hotspot_dict)
        except RuleNotApplicable as e:
            reasons.append(f"{rule_name}: {e}")
            continue

        blocked = find_protected(changes.keys())
        if blocked:
            msg = f"Mudança em módulo crítico exige revisão humana: {', '.join(blocked)}"
            logger.warning(f"🛑 {msg}")
            return PatchResult(status="blocked", rule_applied=rule_name, message=msg)

        try:
            result = git.create_candidate_branch(changes, rule=rule_name, cycle_id=payload.cycle_id or "")
        except NoChanges as e:
            reasons.append(f"{rule_name}: {e}")
            continue
        except GitError as e:
            logger.error(f"❌ Falha git ao aplicar {rule_name}: {e}")
            return PatchResult(status="error", rule_applied=rule_name, message=str(e))

        return PatchResult(
            status="success",
            branch=result["branch"],
            commit=result["commit"],
            file_path=result["files"][0],
            files=result["files"],
            diff=result["diff"],
            rule_applied=rule_name,
            message="Patch gerado e commitado em branch candidato.",
        )

    message = "Nenhuma heurística aplicável: " + "; ".join(reasons)
    logger.info(f"ℹ️ {message}")
    return PatchResult(status="no_applicable_rule", message=message)


@app.post("/promote")
def promote(req: PromoteRequest):
    """Integra um branch aprovado em `main` e cria a tag de deploy."""
    try:
        return {"status": "promoted", **git.promote(req.branch, req.cycle_id or "")}
    except GitError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/rollback")
def rollback(req: RollbackRequest):
    """Reverte em `main` um commit previamente promovido."""
    try:
        return {"status": "rolled_back", **git.rollback(req.commit, req.cycle_id or "")}
    except GitError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
