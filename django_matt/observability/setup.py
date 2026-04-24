"""One-call setup and teardown for the full observability stack (tracing, metrics, logging)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from django_matt.observability.auto import AutoInstrumentor
from django_matt.observability.collectors import metrics_registry
from django_matt.observability.exporters import (
    ConsoleExporter,
    ExporterProtocol,
    JSONExporter,
    MultiExporter,
)
from django_matt.observability.spans import add_span_listener

logger = logging.getLogger("django_matt.observability.setup")

_instrumentor: AutoInstrumentor | None = None
_exporter: MultiExporter | None = None


def _get_config() -> dict[str, Any]:
    return getattr(settings, "DJANGO_MATT_OBSERVABILITY", {})


def _is_debug() -> bool:
    return getattr(settings, "DEBUG", False)


def _build_exporters(config: dict[str, Any]) -> list[ExporterProtocol]:
    exporters: list[ExporterProtocol] = []
    exporter_configs = config.get("EXPORTERS")

    if exporter_configs is None:
        if _is_debug():
            exporters.append(ConsoleExporter(color=True))
        else:
            exporters.append(JSONExporter())
        return exporters

    for exp_config in exporter_configs:
        if isinstance(exp_config, str):
            exp_type = exp_config
            exp_kwargs: dict[str, Any] = {}
        elif isinstance(exp_config, dict):
            exp_type = exp_config.get("type", "console")
            exp_kwargs = {k: v for k, v in exp_config.items() if k != "type"}
        else:
            continue

        if exp_type == "console":
            exporters.append(ConsoleExporter(**exp_kwargs))
        elif exp_type == "json":
            exporters.append(JSONExporter(**exp_kwargs))
        elif exp_type == "prometheus":
            try:
                from django_matt.observability.exporters import PrometheusExporter
                exporters.append(PrometheusExporter())
            except Exception as e:
                logger.warning(f"Could not create PrometheusExporter: {e}")
        elif exp_type == "opentelemetry":
            try:
                from django_matt.observability.exporters import OpenTelemetryExporter
                service_name = exp_kwargs.get("service_name", config.get("SERVICE_NAME", "django-matt"))
                exporters.append(OpenTelemetryExporter(service_name=service_name))
            except Exception as e:
                logger.warning(f"Could not create OpenTelemetryExporter: {e}")

    return exporters


def setup_observability(
    auto: bool = True,
    exporters: list[ExporterProtocol] | None = None,
    service_modules: list[str] | None = None,
) -> AutoInstrumentor:
    global _instrumentor, _exporter

    config = _get_config()
    enabled = config.get("ENABLED", True)

    if not enabled:
        logger.debug("Observability disabled via settings")
        _instrumentor = AutoInstrumentor()
        return _instrumentor

    multi = MultiExporter()
    if exporters:
        for exp in exporters:
            multi.add(exp)
    else:
        for exp in _build_exporters(config):
            multi.add(exp)

    _exporter = multi

    add_span_listener(multi.export)

    _instrumentor = AutoInstrumentor()

    if auto:
        svc_modules = service_modules or config.get("SERVICE_MODULES", [])
        _instrumentor.instrument_all(service_modules=svc_modules)

    logger.info("Observability setup complete")
    return _instrumentor


def get_instrumentor() -> AutoInstrumentor | None:
    return _instrumentor


def get_exporter() -> MultiExporter | None:
    return _exporter


def get_metrics_snapshot() -> dict[str, Any]:
    return metrics_registry.collect_all()


def shutdown_observability() -> None:
    global _instrumentor, _exporter
    if _exporter:
        _exporter.shutdown()
        _exporter = None
    _instrumentor = None
    logger.info("Observability shut down")


__all__ = [
    "get_exporter",
    "get_instrumentor",
    "get_metrics_snapshot",
    "setup_observability",
    "shutdown_observability",
]
