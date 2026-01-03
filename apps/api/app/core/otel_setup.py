"""OpenTelemetry SDK setup and configuration.

This module initializes the OpenTelemetry SDK with appropriate
exporters and resource configuration.
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def setup_opentelemetry() -> None:
    """Initialize OpenTelemetry SDK with appropriate configuration."""
    global _initialized

    if _initialized:
        return

    if not settings.enable_metrics:
        logger.info("OpenTelemetry metrics disabled via configuration")
        return

    try:
        # Create resource with service information
        service_name = settings.otel_service_name or settings.tenant_name
        namespace = (
            settings.metrics_namespace
            or settings.tenant_name.replace(" ", "/")
        )
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.namespace": namespace,
            }
        )

        # Setup tracing
        trace_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(trace_provider)

        # Setup metrics
        metric_exporter = None
        if settings.otel_exporter_otlp_endpoint:
            metrics_endpoint = settings.otel_exporter_otlp_endpoint + "/v1/metrics"
            metric_exporter = OTLPMetricExporter(
                endpoint=metrics_endpoint
            )
            logger.info(
                f"OpenTelemetry metrics exporter configured: "
                f"{metrics_endpoint}"
            )
        else:
            logger.info(
                "OpenTelemetry metrics exporter not configured "
                "(no endpoint specified)"
            )

        if metric_exporter:
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=60000,  # Export every 60 seconds
            )
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader],
            )
        else:
            # Use default meter provider (no-op if no exporter)
            meter_provider = MeterProvider(resource=resource)

        from opentelemetry import metrics
        metrics.set_meter_provider(meter_provider)

        # Setup span exporter if endpoint is configured
        if settings.otel_exporter_otlp_endpoint:
            traces_endpoint = settings.otel_exporter_otlp_endpoint + "/v1/traces"
            span_exporter = OTLPSpanExporter(
                endpoint=traces_endpoint
            )
            span_processor = BatchSpanProcessor(span_exporter)
            trace_provider.add_span_processor(span_processor)
            logger.info(
                f"OpenTelemetry traces exporter configured: "
                f"{traces_endpoint}"
            )

        # Setup logging export if endpoint is configured
        if settings.otel_exporter_otlp_endpoint:
            try:
                from opentelemetry.instrumentation.logging import (
                    LoggingInstrumentor,
                )

                # Instrument logging to send logs via OTLP
                # This captures all Python logging and sends to OTEL Collector
                LoggingInstrumentor().instrument(
                    set_logging_format=False,  # Keep existing formatters
                )
                logger.info(
                    "OpenTelemetry logging instrumentation enabled: %s",
                    settings.otel_exporter_otlp_endpoint,
                )
            except ImportError:
                logger.warning(
                    "OpenTelemetry logging instrumentation not available "
                    "(opentelemetry-instrumentation-logging not installed)"
                )
            except Exception as e:
                logger.warning(
                    "Failed to configure OpenTelemetry logging: %s",
                    e,
                    exc_info=True,
                )

        _initialized = True
        logger.info("OpenTelemetry SDK initialized successfully")

    except Exception as e:
        logger.warning(
            "Failed to initialize OpenTelemetry SDK: %s", e, exc_info=True
        )
        # Continue without OpenTelemetry - metrics will be no-ops

