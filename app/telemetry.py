import logging
import os

logger = logging.getLogger(__name__)
_otel_bootstrapped_pid: int | None = None


def _otel_endpoint() -> str | None:
    return os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )


def otel_enabled() -> bool:
    explicit = os.getenv("OTEL_ENABLED", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    return bool(_otel_endpoint())


def get_otel_status() -> dict[str, object]:
    pid = os.getpid()
    endpoint = _otel_endpoint()
    return {
        "enabled": otel_enabled(),
        "exporter_configured": bool(endpoint),
        "initialized": _otel_bootstrapped_pid == pid,
        "service_name": os.getenv("OTEL_SERVICE_NAME", "dotmac_erp"),
        "scope": "process",
    }


def setup_otel(app=None) -> None:
    global _otel_bootstrapped_pid  # noqa: PLW0603

    if not otel_enabled():
        return

    pid = os.getpid()
    if _otel_bootstrapped_pid == pid:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from app.db import get_engine
    except Exception:
        logger.exception("OpenTelemetry dependencies not available.")
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "dotmac_erp")
    endpoint = _otel_endpoint()
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=get_engine())
    CeleryInstrumentor().instrument()
    _otel_bootstrapped_pid = pid
