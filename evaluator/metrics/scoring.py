from utils.logger import get_logger

logger = get_logger("scoring")

# Regressões acima destes limites invalidam o patch, independentemente do score.
MAX_LATENCY_REGRESSION_PCT = 10.0
MAX_ERROR_REGRESSION_PCT = 10.0
MAX_CPU_REGRESSION_PCT = 30.0
MAX_NEW_ERROR_RATE = 0.01  # erros introduzidos quando o baseline não tinha nenhum


def _detect_regression(b_err, c_err, delta_lat, delta_err, delta_cpu):
    """Retorna a descrição da regressão (ou None) — um patch não pode piorar o sistema."""
    if b_err == 0 and c_err > MAX_NEW_ERROR_RATE:
        return f"Patch introduziu erros (error_rate={c_err:.4f}) onde o baseline não tinha"
    if delta_lat < -MAX_LATENCY_REGRESSION_PCT:
        return f"Regressão de latência: {delta_lat:.1f}%"
    if delta_err < -MAX_ERROR_REGRESSION_PCT:
        return f"Regressão de error rate: {delta_err:.1f}%"
    if delta_cpu < -MAX_CPU_REGRESSION_PCT:
        return f"Regressão de CPU: {delta_cpu:.1f}%"
    return None


def evaluate_metrics(baseline: dict, candidate: dict) -> dict:
    """
    Calcula o delta percentual entre baseline e candidate para cada métrica:
      - delta = (baseline - candidate) / baseline * 100
      - delta positivo = melhoria
      - delta negativo = regressão

    Score ponderado:
      - Latência P95: 50%
      - Error Rate: 30%
      - CPU Usage: 20%

    Guarda zero-baseline: se baseline não contiver dados válidos, rejeita o patch.
    """
    b_lat = baseline.get("latency_p95", 0.0)
    c_lat = candidate.get("latency_p95", 0.0)
    b_err = baseline.get("error_rate", 0.0)
    c_err = candidate.get("error_rate", 0.0)
    b_cpu = baseline.get("cpu_usage", 0.0)
    c_cpu = candidate.get("cpu_usage", 0.0)

    # Zero-baseline guard
    if not any([b_lat, b_err, b_cpu]):
        logger.warning("⚠️ Baseline zerado ou inválido. Rejeitando patch por falta de dados.")
        return {
            "score": 0.0,
            "decision": "reject",
            "delta_latency_pct": 0.0,
            "delta_error_pct": 0.0,
            "delta_cpu_pct": 0.0,
            "confidence": 0.0,
            "reason": "Invalid or zero baseline",
        }

    delta_lat = ((b_lat - c_lat) / b_lat * 100.0) if b_lat > 0 else 0.0
    delta_err = ((b_err - c_err) / b_err * 100.0) if b_err > 0 else 0.0
    delta_cpu = ((b_cpu - c_cpu) / b_cpu * 100.0) if b_cpu > 0 else 0.0

    score = round(delta_lat * 0.5 + delta_err * 0.3 + delta_cpu * 0.2, 2)

    # Determinar recomendação
    regression = _detect_regression(b_err, c_err, delta_lat, delta_err, delta_cpu)
    reason = None
    if regression:
        decision = "reject"
        reason = regression
    elif score >= 10.0:
        decision = "approve_auto"
    elif score > 0.0:
        decision = "review_manual"
    else:
        decision = "reject"

    # Confiança baseada na magnitude e consistência dos sinais
    signals = [s for s in [delta_lat, delta_err, delta_cpu] if s != 0.0]
    confidence = round(min(1.0, len(signals) / 3.0 * (1.0 if score > 0 else 0.5)), 2)

    result = {
        "score": score,
        "decision": decision,
        "delta_latency_pct": round(delta_lat, 2),
        "delta_error_pct": round(delta_err, 2),
        "delta_cpu_pct": round(delta_cpu, 2),
        "confidence": confidence,
        "reason": reason,
        "baseline": baseline,
        "candidate": candidate,
    }

    logger.info(f"✅ Avaliação concluída | Score={score:.2f} | Decisão={decision} | Confidence={confidence}")
    return result
