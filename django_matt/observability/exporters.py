"""Span exporters for the local observability pipeline (console, JSON, Prometheus, OTel)."""

from __future__ import annotations

import io
import logging
import sys
import time
from typing import Any, Protocol, runtime_checkable

import orjson

from django_matt.observability.spans import Span

logger = logging.getLogger("django_matt.observability.exporters")


@runtime_checkable
class ExporterProtocol(Protocol):
    def export(self, span: Span) -> None: ...

    def shutdown(self) -> None: ...


class ConsoleExporter:
    def __init__(self, stream: Any | None = None, color: bool = True) -> None:
        self._stream = stream or sys.stderr
        self._color = color

    def export(self, s: Span) -> None:
        self._print_span(s, indent=0)

    def _print_span(self, s: Span, indent: int) -> None:
        prefix = "  " * indent
        status_icon = "+" if s.status.value == "ok" else "!" if s.status.value == "error" else "?"

        if self._color:
            color = (
                "\033[32m"
                if s.status.value == "ok"
                else "\033[31m"
                if s.status.value == "error"
                else "\033[33m"
            )
            reset = "\033[0m"
            line = f"{prefix}{color}[{status_icon}]{reset} {s.name} ({s.duration_ms:.2f}ms)"
        else:
            line = f"{prefix}[{status_icon}] {s.name} ({s.duration_ms:.2f}ms)"

        if s.tags:
            tag_str = " ".join(
                f"{k}={v}"
                for k, v in s.tags.items()
                if k not in ("error", "error.type", "error.message")
            )
            if tag_str:
                line += f" {tag_str}"

        if s.error:
            line += f" error={type(s.error).__name__}: {s.error}"

        self._stream.write(line + "\n")
        for child in s.children:
            self._print_span(child, indent + 1)

    def shutdown(self) -> None:
        pass


class JSONExporter:
    def __init__(
        self,
        stream: Any | None = None,
        file_path: str | None = None,
    ) -> None:
        self._file_path = file_path
        self._stream = stream
        self._file_handle: io.IOBase | None = None
        if file_path:
            self._file_handle = open(file_path, "ab")

    def export(self, s: Span) -> None:
        data = s.to_dict()
        data["exported_at"] = time.time()
        line = orjson.dumps(data) + b"\n"

        if self._file_handle:
            self._file_handle.write(line)
            self._file_handle.flush()
        elif self._stream:
            if hasattr(self._stream, "buffer"):
                self._stream.buffer.write(line)
            else:
                self._stream.write(line.decode("utf-8"))
        else:
            sys.stdout.buffer.write(line)

    def shutdown(self) -> None:
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None


class PrometheusExporter:
    def __init__(self) -> None:
        try:
            import prometheus_client  # noqa: F401

            self._available = True
        except ImportError:
            self._available = False
            logger.warning("prometheus_client not installed, PrometheusExporter disabled")

        self._histogram: Any = None
        self._counter: Any = None
        self._error_counter: Any = None
        if self._available:
            from prometheus_client import Counter, Histogram

            self._histogram = Histogram(
                "django_matt_span_duration_seconds",
                "Span duration in seconds",
                ["span_name", "status"],
            )
            self._counter = Counter(
                "django_matt_spans_total",
                "Total spans",
                ["span_name", "status"],
            )
            self._error_counter = Counter(
                "django_matt_span_errors_total",
                "Total span errors",
                ["span_name", "error_type"],
            )

    def export(self, s: Span) -> None:
        if not self._available:
            return
        self._export_span(s)

    def _export_span(self, s: Span) -> None:
        status = s.status.value
        duration_s = s.duration_ms / 1000

        self._histogram.labels(span_name=s.name, status=status).observe(duration_s)
        self._counter.labels(span_name=s.name, status=status).inc()

        if s.error:
            self._error_counter.labels(
                span_name=s.name,
                error_type=type(s.error).__name__,
            ).inc()

        for child in s.children:
            self._export_span(child)

    def shutdown(self) -> None:
        pass


class OpenTelemetryExporter:
    def __init__(self, service_name: str = "django-matt") -> None:
        self._available = False
        self._tracer: Any = None
        try:
            from opentelemetry import trace as otel_trace
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider

            resource = Resource.create({SERVICE_NAME: service_name})
            provider = TracerProvider(resource=resource)
            otel_trace.set_tracer_provider(provider)
            self._tracer = otel_trace.get_tracer(service_name)
            self._available = True
        except ImportError:
            logger.warning("opentelemetry-sdk not installed, OpenTelemetryExporter disabled")

    def export(self, s: Span) -> None:
        if not self._available or not self._tracer:
            return
        self._export_span(s)

    def _export_span(self, s: Span) -> None:
        from opentelemetry.trace import StatusCode

        with self._tracer.start_as_current_span(s.name) as otel_span:
            for k, v in s.tags.items():
                try:
                    otel_span.set_attribute(k, v)
                except Exception:
                    otel_span.set_attribute(k, str(v))

            if s.error:
                otel_span.record_exception(s.error)
                otel_span.set_status(StatusCode.ERROR, str(s.error))
            elif s.status.value == "ok":
                otel_span.set_status(StatusCode.OK)

            for child in s.children:
                self._export_span(child)

    def shutdown(self) -> None:
        pass


class MultiExporter:
    def __init__(self, exporters: list[ExporterProtocol] | None = None) -> None:
        self._exporters: list[ExporterProtocol] = exporters or []

    def add(self, exporter: ExporterProtocol) -> None:
        self._exporters.append(exporter)

    def export(self, s: Span) -> None:
        for exporter in self._exporters:
            try:
                exporter.export(s)
            except Exception as e:
                logger.error(f"Exporter {type(exporter).__name__} failed: {e}")

    def shutdown(self) -> None:
        for exporter in self._exporters:
            try:
                exporter.shutdown()
            except Exception as e:
                logger.error(f"Exporter {type(exporter).__name__} shutdown failed: {e}")


__all__ = [
    "ConsoleExporter",
    "ExporterProtocol",
    "JSONExporter",
    "MultiExporter",
    "OpenTelemetryExporter",
    "PrometheusExporter",
]
