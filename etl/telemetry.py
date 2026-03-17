from loguru import logger
from utils import timer, monitor_perf

from shared.config import Config

with timer("telemetry imports (lazy)"):
    # Heavy imports moved to init_telemetry
    pass

_TELEMETRY_INITIALIZED = False


@monitor_perf
def init_telemetry():
    """Initializes OpenTelemetry instrumentation if enabled."""
    global _TELEMETRY_INITIALIZED
    if _TELEMETRY_INITIALIZED:
        return

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource

    if not Config.OTEL_ENABLED:
        # Mark as initialized to avoid repeated checks/logs
        _TELEMETRY_INITIALIZED = True
        logger.info("OpenTelemetry is disabled.")
        return

    logger.info(
        f"Initializing OpenTelemetry with endpoint: {Config.OTEL_EXPORTER_OTLP_ENDPOINT}"
    )

    resource = Resource(attributes={"service.name": "summagram_app"})

    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    try:
        exporter = OTLPSpanExporter(
            endpoint=Config.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True
        )
        span_processor = BatchSpanProcessor(exporter)
        tracer_provider.add_span_processor(span_processor)

        # Instrument LlamaIndex
        # DISABLED: Causes Pydantic validation error with streaming responses (openinference-instrumentation-llama-index issue)
        # LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

        logger.info(
            "OpenTelemetry initialization successful (LlamaIndex instrumentation disabled due to bug)."
        )
        _TELEMETRY_INITIALIZED = True
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
