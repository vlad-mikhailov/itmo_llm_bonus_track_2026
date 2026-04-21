"""OpenTelemetry initialization: TracerProvider, exporters, global tracer."""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_SERVICE_NAME = "finops-ai-gateway"


def init_telemetry() -> None:
    """Set up the global TracerProvider.

    In dev mode (OTEL_EXPORTER=console or unset) spans go to stdout.
    When OTEL_EXPORTER_OTLP_ENDPOINT is set, spans are sent via OTLP/gRPC.
    """
    resource = Resource.create({"service.name": _SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        # Lazy import: opentelemetry-exporter-otlp is optional
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-untyped]
            OTLPSpanExporter,
        )

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer scoped to *name* (e.g. module path)."""
    return trace.get_tracer(name)
