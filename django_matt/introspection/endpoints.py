from __future__ import annotations

import sys
import time

import django
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import path

import orjson

import django_matt
from django_matt.introspection.registry import ComponentStatus, registry
from django_matt.introspection.report import generate_report


async def health_view(request: HttpRequest) -> HttpResponse:
    result = await registry.health_check()
    ok = result.status != ComponentStatus.UNHEALTHY
    body = orjson.dumps({"status": "ok" if ok else "error"})
    return HttpResponse(
        body,
        content_type="application/json",
        status=200 if ok else 503,
    )


async def health_detailed_view(request: HttpRequest) -> HttpResponse:
    if not await _is_authenticated(request):
        return HttpResponse(
            orjson.dumps({"error": "authentication required"}),
            content_type="application/json",
            status=401,
        )

    result = await registry.health_check()
    payload = {
        "status": result.status.value,
        "timestamp": result.timestamp,
        "components": {
            name: {
                "status": comp.status.value,
                "component_type": comp.component_type,
                "latency_ms": comp.latency_ms,
                "details": comp.details,
                "error": comp.error,
                "critical": comp.critical,
            }
            for name, comp in result.components.items()
        },
    }
    status_code = 200 if result.status != ComponentStatus.UNHEALTHY else 503
    return HttpResponse(
        orjson.dumps(payload),
        content_type="application/json",
        status=status_code,
    )


async def health_ready_view(request: HttpRequest) -> HttpResponse:
    result = await registry.health_check()
    critical_ok = all(
        comp.status != ComponentStatus.UNHEALTHY
        for comp in result.components.values()
        if comp.critical
    )
    body = orjson.dumps({"ready": critical_ok})
    return HttpResponse(
        body,
        content_type="application/json",
        status=200 if critical_ok else 503,
    )


async def health_live_view(request: HttpRequest) -> HttpResponse:
    body = orjson.dumps({"alive": True, "timestamp": time.time()})
    return HttpResponse(body, content_type="application/json", status=200)


async def info_view(request: HttpRequest) -> HttpResponse:
    report = await generate_report()
    body = orjson.dumps(report.model_dump())
    return HttpResponse(body, content_type="application/json", status=200)


async def _is_authenticated(request: HttpRequest) -> bool:
    user = getattr(request, "user", None)
    if user is None:
        return False
    is_auth = getattr(user, "is_authenticated", False)
    if callable(is_auth):
        return is_auth()
    return bool(is_auth)


def get_health_urls(prefix: str = "health") -> list:
    return [
        path(f"{prefix}/", health_view, name="introspection-health"),
        path(f"{prefix}/detailed/", health_detailed_view, name="introspection-health-detailed"),
        path(f"{prefix}/ready/", health_ready_view, name="introspection-health-ready"),
        path(f"{prefix}/live/", health_live_view, name="introspection-health-live"),
        path("_info/", info_view, name="introspection-info"),
    ]
