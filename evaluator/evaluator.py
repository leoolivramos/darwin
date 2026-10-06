from datetime import datetime
from fastapi import FastAPI, Response, HTTPException
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from models import EvaluationRequest, EvaluationResult, Recommendation
from metrics.scoring import evaluate_metrics
from utils.report_builder import build_report
from utils.logger import get_logger

app = FastAPI(title="Darwin - Evaluator", version="1.0.0")
logger = get_logger("evaluator")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "evaluator",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/evaluate", response_model=EvaluationResult)
async def evaluate_patch(req: EvaluationRequest):
    """
    Avalia a variação de desempenho entre baseline e candidate:
      - Calcula deltas percentuais
      - Aplica pontuação ponderada
      - Emite recomendação: approve_auto, review_manual ou reject
      - Constrói relatório auditável
    """
    logger.info(f"🔬 Avaliação iniciada para o ciclo: {req.cycle_id or 'unknown'}")

    try:
        baseline_dict = req.baseline.model_dump()
        candidate_dict = req.candidate.model_dump()

        result = evaluate_metrics(baseline_dict, candidate_dict)
        report = build_report(result)

        recommendation_str = result.get("decision", "reject")
        try:
            recommendation = Recommendation(recommendation_str)
        except ValueError:
            recommendation = Recommendation.REJECT

        logger.info(f"📊 Avaliação concluída. Cycle: {req.cycle_id} | Score: {result.get('score')} | Rec: {recommendation}")

        return EvaluationResult(
            score=result.get("score", 0.0),
            recommendation=recommendation,
            delta_latency_pct=result.get("delta_latency_pct", 0.0),
            delta_error_pct=result.get("delta_error_pct", 0.0),
            delta_cpu_pct=result.get("delta_cpu_pct", 0.0),
            confidence=result.get("confidence", 0.0),
            report=report,
            cycle_id=req.cycle_id,
        )

    except Exception as e:
        logger.error(f"❌ Erro durante avaliação: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno no Evaluator: {str(e)}")


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
