from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Darwin - Telemetry Collector",
    version="1.0.0",
    description="OpenTelemetry metrics, traces and logs collector"
)

# Prometheus metrics
traces_counter = Counter(
    'telemetry_traces_total',
    'Total traces collected',
    ['service']
)

metrics_counter = Counter(
    'telemetry_metrics_total',
    'Total metrics collected',
    ['metric_type']
)

logs_counter = Counter(
    'telemetry_logs_total',
    'Total logs collected',
    ['service', 'level']
)

collection_latency = Histogram(
    'telemetry_collection_latency_seconds',
    'Time taken to collect telemetry'
)

# Configure OpenTelemetry
def setup_tracing():
    """Setup Jaeger tracing"""
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.getenv("JAEGER_HOST", "jaeger"),
        agent_port=int(os.getenv("JAEGER_PORT", 6831)),
    )
    
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )

def setup_metrics():
    """Setup Prometheus metrics"""
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)

# Initialize tracing and metrics
try:
    setup_tracing()
    setup_metrics()
    logger.info("✅ OpenTelemetry configured successfully")
except Exception as e:
    logger.warning(f"⚠️ OpenTelemetry setup warning: {e}")

# Instrument libraries
RequestsInstrumentor().instrument()
FastAPIInstrumentor().instrument_app(app)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "telemetry-collector",
        "version": "1.0.0"
    }

@app.post("/traces")
async def receive_traces(data: dict):
    """Receive traces from services"""
    try:
        traces_counter.labels(service=data.get("service", "unknown")).inc()
        logger.info(f"📊 Trace received from {data.get('service')}")
        return {"status": "accepted", "trace_id": data.get("trace_id")}
    except Exception as e:
        logger.error(f"❌ Error processing trace: {e}")
        return {"status": "error", "message": str(e)}, 400

@app.post("/metrics")
async def receive_metrics(data: dict):
    """Receive metrics from services"""
    try:
        metric_type = data.get("type", "unknown")
        metrics_counter.labels(metric_type=metric_type).inc()
        logger.info(f"📊 Metric received: {metric_type}")
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"❌ Error processing metric: {e}")
        return {"status": "error", "message": str(e)}, 400

@app.post("/logs")
async def receive_logs(data: dict):
    """Receive logs from services"""
    try:
        service = data.get("service", "unknown")
        level = data.get("level", "INFO")
        logs_counter.labels(service=service, level=level).inc()
        logger.info(f"📋 Log received from {service} [{level}]")
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"❌ Error processing log: {e}")
        return {"status": "error", "message": str(e)}, 400

@app.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics"""
    return generate_latest()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
