from datetime import datetime


def build_report(result: dict) -> dict:
    """
    Gera um relatório final padronizado e auditável para armazenamento no Silo / DB.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "decision": result.get("decision", "reject"),
            "score": result.get("score", 0.0),
            "confidence": result.get("confidence", 0.0),
            "reason": result.get("reason"),
        },
        "details": {
            "delta_latency_pct": result.get("delta_latency_pct", 0.0),
            "delta_error_pct": result.get("delta_error_pct", 0.0),
            "delta_cpu_pct": result.get("delta_cpu_pct", 0.0),
        },
        "metadata": {
            "baseline": result.get("baseline", {}),
            "candidate": result.get("candidate", {}),
        },
    }
