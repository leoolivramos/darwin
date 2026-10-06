import logging
import os
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger("telemetry_collector")

app = FastAPI(
    title="Darwin - Telemetry Collector",
    version="1.0.0",
    description="OpenTelemetry metrics, traces and logs collector",
)

# Prometheus metrics
traces_counter = Counter(
    "telemetry_traces_total",
    "Total traces collected",
    ["service"],
)

metrics_counter = Counter(
    "telemetry_metrics_total",
    "Total metrics collected",
    ["metric_type"],
)

logs_counter = Counter(
    "telemetry_logs_total",
    "Total logs collected",
    ["service", "level"],
)

collection_latency = Histogram(
    "telemetry_collection_latency_seconds",
    "Time taken to collect telemetry",
)


def setup_tracing():
    """Setup tracing via OpenTelemetry if available."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        trace.set_tracer_provider(provider)

        jaeger_host = os.getenv("JAEGER_HOST", "jaeger")
        jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))

        exporter = None
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=f"{jaeger_host}:4317", insecure=True)
        except Exception:
            try:
                from opentelemetry.exporter.jaeger.thrift import JaegerExporter
                exporter = JaegerExporter(agent_host_name=jaeger_host, agent_port=jaeger_port)
            except Exception as e:
                logger.debug(f"Nenhum exportador Jaeger/OTLP ativo: {e}")

        if exporter:
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OpenTelemetry tracing configurado")
    except Exception as e:
        logger.warning(f"Aviso na inicialização do tracing: {e}")


def setup_instrumentation():
    """Instrument libraries if available."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument_app(app)
    except Exception as e:
        logger.debug(f"FastAPIInstrumentor não configurado: {e}")

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        RequestsInstrumentor().instrument()
    except Exception as e:
        logger.debug(f"RequestsInstrumentor não configurado: {e}")


# Initialize
setup_tracing()
setup_instrumentation()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "telemetry-collector",
        "version": "1.0.0",
    }


@app.post("/traces")
async def receive_traces(data: dict):
    """Receive traces from services."""
    try:
        service = data.get("service", "unknown")
        traces_counter.labels(service=service).inc()
        logger.info(f"Trace recebido de {service}")
        return {"status": "accepted", "trace_id": data.get("trace_id")}
    except Exception as e:
        logger.error(f"Erro processando trace: {e}")
        return Response(content=f'{{"status":"error","message":"{e}"}}', status_code=400, media_type="application/json")


@app.post("/metrics")
async def receive_metrics(data: dict):
    """Receive metrics from services."""
    try:
        metric_type = data.get("type", "unknown")
        metrics_counter.labels(metric_type=metric_type).inc()
        logger.info(f"Métrica recebida: {metric_type}")
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"Erro processando métrica: {e}")
        return Response(content=f'{{"status":"error","message":"{e}"}}', status_code=400, media_type="application/json")


@app.post("/logs")
async def receive_logs(data: dict):
    """Receive logs from services."""
    try:
        service = data.get("service", "unknown")
        level = data.get("level", "INFO")
        logs_counter.labels(service=service, level=level).inc()
        logger.info(f"Log recebido de {service} [{level}]")
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"Erro processando log: {e}")
        return Response(content=f'{{"status":"error","message":"{e}"}}', status_code=400, media_type="application/json")


@app.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
