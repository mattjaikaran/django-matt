"""
AI-powered request lifecycle tracing for django-matt routes.

Provides ``trace_route(api_instance, path, method)`` that performs deep
source-code analysis of controller and service layers to produce a
human-readable request flow tree.

Usage:
    from django_matt.ai.explain import trace_route
    trace = trace_route(api, "/api/orders/", "POST")
    print(trace.render())
"""

from __future__ import annotations

import ast
import inspect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.conf import settings

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TraceNode:
    """A single node in the request lifecycle tree."""

    label: str
    detail: str = ""
    children: list[TraceNode] = field(default_factory=list)
    is_leaf: bool = True

    def add_child(self, node: TraceNode) -> None:
        self.children.append(node)
        self.is_leaf = False


@dataclass
class RouteMatch:
    """Resolved route information."""

    path: str
    method: str
    endpoint: Any
    endpoint_name: str
    controller_class: type | None = None
    controller_method_name: str | None = None
    response_model: type | None = None
    status_code: int = 200
    tags: list[str] = field(default_factory=list)
    source_file: str = ""
    source_code: str = ""


@dataclass
class RenderableTrace:
    """Wraps a TraceNode tree with rendering methods."""

    root: TraceNode

    def render(self) -> str:
        """Render as a Unicode box-drawing tree."""
        return render_tree(self.root)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DEPENDENCY_PATTERNS: list[tuple[str, str, str]] = [
    # (module substring, pattern label, detail hint)
    ("stripe", "stripe", "Stripe payment processing"),
    ("paypal", "paypal", "PayPal payment processing"),
    ("polar", "polar", "Polar.sh payment processing"),
    ("django_matt.billing", "django_matt.billing", "Billing module"),
    ("django_matt.email", "django_matt.email", "Email sending"),
    ("django_matt.notifications", "django_matt.notifications", "Push notifications"),
    ("django_matt.messaging", "django_matt.messaging", "Real-time messaging"),
    ("django_matt.analytics", "django_matt.analytics", "Analytics tracking"),
    ("django.core.cache", "django.core.cache", "Django cache backend"),
    ("django_matt.ai.cache", "django_matt.ai.cache", "AI semantic cache"),
    ("django_matt.ai.embeddings", "django_matt.ai.embeddings", "AI embeddings"),
    ("django_matt.ai.rag", "django_matt.ai.rag", "RAG pipeline"),
    ("boto3", "boto3 / AWS", "AWS SDK"),
    ("google.cloud", "GCP", "Google Cloud SDK"),
    ("resend", "resend", "Resend email API"),
    ("sendgrid", "sendgrid", "SendGrid email API"),
    ("mailgun", "mailgun", "Mailgun email API"),
    ("celery", "celery", "Async task queue"),
    ("django_matt.tasks", "django_matt.tasks", "Background task runner"),
    ("redis", "redis", "Redis cache/broker"),
    ("httpx", "httpx", "Outbound HTTP calls"),
    ("requests", "requests", "Outbound HTTP calls"),
    ("openai", "openai", "OpenAI API"),
    ("anthropic", "anthropic", "Anthropic API"),
    ("django_matt.ai.providers", "AI provider", "LLM inference"),
]


def trace_route(
    api_instance: Any,
    path: str,
    method: str = "GET",
) -> RenderableTrace:
    """Trace the full request lifecycle for a route.

    Args:
        api_instance: A ``DjangoMattAPI`` (or ``APIRouter``) instance.
        path: URL path, e.g. ``"/api/orders/"``.
        method: HTTP method, e.g. ``"POST"``.

    Returns:
        Root ``TraceNode`` of the lifecycle tree.
    """
    method = method.upper()
    match = _resolve_route(api_instance, path, method)

    root = TraceNode(label=f"{method} {path}")

    # ── Middleware ────────────────────────────────────────────────
    _trace_middleware(root)

    # ── Auth / permissions / throttle ─────────────────────────────
    _trace_auth_layer(root, match)

    # ── Controller → service → ORM ───────────────────────────────
    _trace_business_layer(root, match)

    # ── Response ──────────────────────────────────────────────────
    _trace_response(root, match)

    # ── Dependencies ──────────────────────────────────────────────
    _trace_dependencies(root, match)

    return RenderableTrace(root=root)


def render_tree(root: TraceNode) -> str:
    """Render a ``TraceNode`` tree as a Unicode box-drawing string."""
    lines: list[str] = []

    def _walk(node: TraceNode, prefix: str, is_last: bool, is_root: bool) -> None:
        if is_root:
            lines.append(node.label)
        else:
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{node.label}")

        child_prefix = prefix + ("    " if is_last else "│   ")

        for i, child in enumerate(node.children):
            _walk(child, child_prefix, i == len(node.children) - 1, False)

    _walk(root, "", True, True)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Route resolution
# ---------------------------------------------------------------------------


def _resolve_route(api_instance: Any, path: str, method: str) -> RouteMatch:
    """Find the endpoint that handles *path* + *method*."""
    norm = path.rstrip("/") or "/"

    # 1. Decorator routes
    for route in getattr(api_instance, "routes", []):
        rpath = route["path"].rstrip("/") or "/"
        if _paths_match(rpath, norm) and method in route.get("methods", ["GET"]):
            ep = route["endpoint"]
            src_file, src_code = _get_source(ep)
            return RouteMatch(
                path=route["path"],
                method=method,
                endpoint=ep,
                endpoint_name=getattr(ep, "__name__", str(ep)),
                response_model=route.get("response_model"),
                status_code=route.get("status_code", 200),
                tags=route.get("tags", []),
                source_file=src_file,
                source_code=src_code,
            )

    # 2. Controller routes
    prefix = getattr(api_instance, "prefix", "")
    for ctrl_cls in getattr(api_instance, "controllers", []):
        ctrl_prefix = getattr(ctrl_cls, "prefix", "")
        full_prefix = prefix + ctrl_prefix

        for mname in dir(ctrl_cls):
            if mname.startswith("_"):
                continue
            meth = getattr(ctrl_cls, mname, None)
            route_info = getattr(meth, "_route_info", None)
            if route_info is None:
                continue
            rpath = (full_prefix + route_info["path"]).rstrip("/") or "/"
            rmethods = route_info.get("methods", ["GET"])
            if _paths_match(rpath, norm) and method in rmethods:
                src_file, src_code = _get_source(meth)
                return RouteMatch(
                    path=route_info["path"],
                    method=method,
                    endpoint=meth,
                    endpoint_name=mname,
                    controller_class=ctrl_cls,
                    controller_method_name=mname,
                    response_model=route_info.get("response_model"),
                    status_code=route_info.get("status_code", 200),
                    tags=route_info.get("tags", []),
                    source_file=src_file,
                    source_code=src_code,
                )

    # Fallback: unresolved
    return RouteMatch(
        path=path,
        method=method,
        endpoint=None,
        endpoint_name="(unresolved)",
    )


def _paths_match(pattern: str, actual: str) -> bool:
    """Check if *actual* matches *pattern* accounting for Django path params."""
    if pattern == actual:
        return True

    # Convert Django <type:name> patterns to regex
    regex_parts = []
    for segment in pattern.strip("/").split("/"):
        if segment.startswith("<") and segment.endswith(">"):
            inner = segment[1:-1]
            if ":" in inner:
                _typ, _name = inner.split(":", 1)
                regex_parts.append(r"[^/]+")
            else:
                regex_parts.append(r"[^/]+")
        else:
            regex_parts.append(re.escape(segment))
    regex = "^/" + "/".join(regex_parts) + "/?$"
    return bool(re.match(regex, actual + "/" if not actual.endswith("/") else actual))


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------


def _get_source(func: Any) -> tuple[str, str]:
    """Return (file_path, source_code) for a function or class."""
    try:
        src = inspect.getsource(func)
        f = inspect.getfile(func)
        return f, src
    except (OSError, TypeError):
        return "", ""


# ---------------------------------------------------------------------------
# Middleware tracing
# ---------------------------------------------------------------------------


def _trace_middleware(root: TraceNode) -> None:
    """Add middleware nodes to the tree."""
    try:
        mw_list = settings.MIDDLEWARE
    except Exception:
        return

    cors_added = False
    for mw_path in mw_list:
        name = mw_path.rsplit(".", 1)[-1]

        # CORS
        if "CORS" in name or "Cors" in name:
            if not cors_added:
                root.add_child(
                    TraceNode(label="CORS middleware", detail="Cross-origin request handling")
                )
                cors_added = True
            continue

        # Security
        if "Security" in name:
            root.add_child(TraceNode(label="Security middleware", detail=name))
            continue

        # CSRF
        if "CSRF" in name or "Csrf" in name:
            root.add_child(TraceNode(label="CSRF middleware", detail=name))
            continue

        # Session
        if "Session" in name:
            root.add_child(TraceNode(label="Session middleware", detail=name))
            continue

        # Auth
        if "Auth" in name or "auth" in mw_path.lower():
            root.add_child(TraceNode(label="Authentication middleware", detail=name))
            continue

        # Cache
        if "Cache" in name or "cache" in mw_path.lower():
            root.add_child(TraceNode(label="Cache middleware", detail=name))
            continue

        # Radix / rate
        if "Radix" in name:
            root.add_child(
                TraceNode(label="Radix router middleware", detail="Fast Rust-based dispatch")
            )
            continue

        if "Throttle" in name or "RateLimit" in name or "throttle" in mw_path.lower():
            root.add_child(TraceNode(label="Rate limiting", detail=name))
            continue

    # Default Django middleware that's always present
    root.add_child(
        TraceNode(label="Request enters Django", detail="WSGI/ASGI handler → middleware stack")
    )


# ---------------------------------------------------------------------------
# Auth / permissions / throttle tracing
# ---------------------------------------------------------------------------


def _trace_auth_layer(root: TraceNode, match: RouteMatch) -> None:
    """Inspect controller class attributes for auth configuration."""
    ctrl = match.controller_class
    if ctrl is None and match.endpoint is not None:
        # For decorator routes, the endpoint may have __self__
        ctrl = getattr(match.endpoint, "__self__", None)
        if ctrl is not None:
            ctrl = type(ctrl)

    if ctrl is None:
        return

    # Auth classes
    auth_classes = getattr(ctrl, "authentication_classes", [])
    for ac in auth_classes:
        name = ac.__name__ if isinstance(ac, type) else ac.__class__.__name__
        root.add_child(TraceNode(label="JWT authentication", detail=name))
    if not auth_classes:
        # Check for JWT decorators on the method
        ep = match.endpoint
        if ep and (getattr(ep, "_jwt_required", False) or getattr(ep, "_jwt_optional", False)):
            required = "required" if getattr(ep, "_jwt_required", False) else "optional"
            root.add_child(TraceNode(label=f"JWT authentication ({required})", detail=""))

    # Permission classes
    perm_classes = getattr(ctrl, "permission_classes", [])
    for pc in perm_classes:
        name = pc.__name__ if isinstance(pc, type) else pc.__class__.__name__
        root.add_child(TraceNode(label=f"Permission check: {name}", detail=""))

    # Throttle classes
    throttle_classes = getattr(ctrl, "throttle_classes", [])
    for tc in throttle_classes:
        name = tc.__name__ if isinstance(tc, type) else tc.__class__.__name__
        rate = getattr(tc, "rate", "")
        detail = f"{rate}" if rate else ""
        root.add_child(TraceNode(label=f"Rate limiting: {name}", detail=detail))


# ---------------------------------------------------------------------------
# Business layer (controller → service → ORM)
# ---------------------------------------------------------------------------


def _trace_business_layer(root: TraceNode, match: RouteMatch) -> None:
    """Analyze source to trace controller → service → ORM flow."""
    src = match.source_code
    if not src:
        if match.endpoint_name and match.endpoint_name != "(unresolved)":
            root.add_child(TraceNode(label=match.endpoint_name, detail="Controller entry point"))
        return

    try:
        tree = ast.parse(src)
    except SyntaxError:
        root.add_child(TraceNode(label=match.endpoint_name, detail="Controller entry point"))
        return

    # Find the function definition
    func_node = _find_function(tree, match)
    if func_node is None:
        root.add_child(TraceNode(label=match.endpoint_name, detail="Controller entry point"))
        return

    # Controller node
    ctrl_label = match.endpoint_name
    if match.controller_class:
        ctrl_label = f"{match.controller_class.__name__}.{match.endpoint_name}"
    ctrl_node = TraceNode(label=ctrl_label, detail="Controller entry point")
    root.add_child(ctrl_node)

    # Collect service calls and ORM calls from the function body
    service_calls = _extract_service_calls(func_node)
    orm_calls = _extract_orm_calls(func_node)
    dependency_calls = _extract_provider_calls(func_node)

    for sc in service_calls:
        svc_node = TraceNode(label=sc["call"], detail=sc.get("detail", ""))
        ctrl_node.add_child(svc_node)

        # Try to find the service source and trace its method calls
        svc_method_calls = _trace_service_method(sc)
        if svc_method_calls:
            for smc in svc_method_calls:
                svc_node.add_child(TraceNode(label=smc["call"], detail=smc.get("detail", "")))
        # Generic ORM indicator
        elif sc.get("is_orm", False):
            svc_node.add_child(TraceNode(label="Django ORM query", detail=sc.get("model", "")))

    # Fallback: if no service calls found but ORM calls exist
    if not service_calls and orm_calls:
        for oc in orm_calls:
            ctrl_node.add_child(TraceNode(label=oc["call"], detail=oc.get("detail", "")))

    # Provider/dependency calls (stripe, email, etc.)
    for dc in dependency_calls:
        ctrl_node.add_child(TraceNode(label=dc["call"], detail=dc.get("detail", "")))


def _find_function(
    tree: ast.AST, match: RouteMatch
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Locate the function/async function node in the AST."""
    target = match.endpoint_name
    # If the source is a standalone function, the tree IS the function
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == target:
                return node
    # Single-function source where the module just wraps one def
    if isinstance(tree, ast.Module) and len(tree.body) == 1:
        node = tree.body[0]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def _extract_service_calls(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, str]]:
    """Find service method calls in the function body."""
    calls: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            call_str = _call_to_string(node)
            if call_str in seen:
                continue

            # Detect patterns like self.service.create_order(...)
            if _is_service_call(node):
                seen.add(call_str)
                calls.append({"call": call_str, "is_orm": False})
            # Detect ORM patterns: Model.objects.filter(...), Model.objects.create(...)
            elif _is_orm_call(node):
                seen.add(call_str)
                model = _extract_orm_model(node)
                calls.append({"call": call_str, "is_orm": True, "model": model})

    return calls


def _call_to_string(node: ast.Call) -> str:
    """Render a call AST node to a readable string."""
    parts: list[str] = []

    def _render(n: ast.AST) -> str:
        if isinstance(n, ast.Name):
            return n.id
        if isinstance(n, ast.Attribute):
            return f"{_render(n.value)}.{n.attr}"
        if isinstance(n, ast.Call):
            args = ", ".join(_render(a) for a in n.args[:2])
            if len(n.args) > 2:
                args += ", …"
            return f"{_render(n.func)}({args})"
        if isinstance(n, ast.Constant):
            if n.value is None:
                return "None"
            if isinstance(n.value, str):
                return f'"{n.value[:30]}"' if len(n.value) > 30 else repr(n.value)
            return str(n.value)
        if isinstance(n, ast.Subscript):
            return f"{_render(n.value)}[{_render(n.slice)}]"
        if isinstance(n, ast.List):
            return "[…]"
        if isinstance(n, ast.Dict):
            return "{…}"
        if isinstance(n, ast.Lambda):
            return "lambda …"
        if isinstance(n, ast.BinOp):
            return f"({_render(n.left)} {_op(n.op)} {_render(n.right)})"
        return "…"

    def _op(op: ast.operator) -> str:
        mapping = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Mod: "%",
            ast.Pow: "**",
            ast.FloorDiv: "//",
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.Gt: ">",
            ast.LtE: "<=",
            ast.GtE: ">=",
        }
        return mapping.get(type(op), "?")

    try:
        return _render(node)
    except Exception:
        return "…"


def _is_service_call(node: ast.Call) -> bool:
    """Check if a call looks like a service method invocation."""
    func = node.func
    if isinstance(func, ast.Attribute):
        attr_chain = _get_attr_chain(func.value)
        # self.service.method(), self._svc.method(), self._order_svc.method()
        for part in attr_chain:
            if "service" in part.lower() or "svc" in part.lower():
                return True
        # module.ServiceClass.method() — static-like
        if any(p[0].isupper() and "Service" in p for p in attr_chain):
            return True
    return False


def _is_orm_call(node: ast.Call) -> bool:
    """Check if a call looks like a Django ORM method."""
    func = node.func
    if isinstance(func, ast.Attribute):
        orm_methods = {
            "filter",
            "exclude",
            "get",
            "all",
            "create",
            "acreate",
            "update",
            "delete",
            "adelete",
            "save",
            "asave",
            "select_related",
            "prefetch_related",
            "annotate",
            "aggregate",
            "order_by",
            "values",
            "values_list",
            "first",
            "last",
            "count",
            "exists",
            "aexists",
            "bulk_create",
            "abulk_create",
            "get_or_create",
            "aget_or_create",
            "update_or_create",
            "aupdate_or_create",
        }
        if func.attr in orm_methods:
            return True
    return False


def _extract_orm_model(node: ast.Call) -> str:
    """Extract model name from an ORM call like ``Order.objects.filter()``."""
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr == "objects":
            return "(direct)"
        chain = _get_attr_chain(func.value)
        if chain:
            # Look for "Model.objects" pattern, take the model name
            for i, part in enumerate(chain):
                if part == "objects" and i > 0:
                    return chain[i - 1]
            return chain[-1] if chain[-1] != "objects" else chain[0] if len(chain) > 1 else ""
    return ""


def _get_attr_chain(node: ast.AST) -> list[str]:
    """Flatten an attribute chain to name parts. ``self.svc.method`` → ['self','svc','method']."""
    parts: list[str] = []

    def _walk(n: ast.AST) -> None:
        if isinstance(n, ast.Name):
            parts.append(n.id)
        elif isinstance(n, ast.Attribute):
            _walk(n.value)
            parts.append(n.attr)
        elif isinstance(n, ast.Call):
            _walk(n.func)

    _walk(node)
    return parts


def _extract_provider_calls(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, str]]:
    """Detect calls to external service providers."""
    calls: list[dict[str, str]] = []
    seen: set[str] = set()

    provider_indicators = [
        "stripe",
        "paypal",
        "billing",
        "email",
        "send_email",
        "sendgrid",
        "mailgun",
        "resend",
        "ses",
        "push",
        "notify",
        "cache",
        "redis",
        "celery",
        "task",
        "fetch",
        "httpx",
        "request",
        "openai",
        "anthropic",
        "embed",
        "rag",
        "vector",
    ]

    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            call_str = _call_to_string(node)
            if call_str in seen:
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                full = _get_attr_chain(func)
                for token in full:
                    token_lower = token.lower()
                    if any(ind in token_lower for ind in provider_indicators):
                        seen.add(call_str)
                        calls.append({"call": call_str, "detail": ""})
                        break

    return calls


def _trace_service_method(sc: dict[str, str]) -> list[dict[str, str]]:
    """Try to find the source of a service method and trace its ORM calls."""
    call = sc.get("call", "")
    # Parse "self.service.method_name(args)" → try to find the service class
    # We can't reliably resolve dynamically, but we can look for service classes
    # by name in the project and check if they have the called method
    if sc.get("is_orm"):
        return []

    # Try extracting service class name from the call
    parts = call.split("(")[0].split(".")
    if len(parts) < 3:
        return []

    method_name = parts[-1]
    # The call pattern is typically self.<service_attr>.<method>
    # e.g., self.order_service.create_order
    # or OrderService.create_order
    svc_attr = parts[-2] if len(parts) >= 2 else ""

    # Heuristic: if svc_attr ends with "Service" or contains "service"/"svc"
    # Look for the service class via inspection
    svc_class = _find_service_class(svc_attr)
    if svc_class is None:
        return []

    return _trace_service_method_source(svc_class, method_name)


def _find_service_class(name_hint: str) -> type | None:
    """Try to locate a service class by name hint."""
    candidates = []

    # Search common service locations
    service_dirs: list[str] = []
    try:
        import django_matt

        base = Path(django_matt.__file__).parent
    except Exception:
        return None

    for py_file in base.rglob("services.py"):
        service_dirs.append(str(py_file))
    for py_file in base.rglob("**/services/__init__.py"):
        service_dirs.append(str(py_file))

    for svc_path in service_dirs:
        try:
            module_path = _path_to_module(svc_path, base)
            mod = __import__(module_path, fromlist=["*"])
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if not isinstance(obj, type):
                    continue
                # Match by name
                if name_hint.lower() in attr_name.lower() or attr_name.lower() in name_hint.lower():
                    candidates.append((attr_name, obj))
        except Exception:
            pass

    if candidates:
        return candidates[0][1]
    return None


def _path_to_module(filepath: str, base: Path) -> str:
    """Convert a file path to a Python module path."""
    rel = Path(filepath).relative_to(base.parent)
    parts = list(rel.parts)
    parts[-1] = parts[-1].replace(".py", "")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _trace_service_method_source(svc_class: type, method_name: str) -> list[dict[str, str]]:
    """Extract ORM calls from a service method source."""
    method = getattr(svc_class, method_name, None)
    if method is None:
        return []

    try:
        src = inspect.getsource(method)
        tree = ast.parse(src)
    except (OSError, TypeError, SyntaxError):
        return []

    # Find the function definition
    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == method_name:
                func_node = node
                break
    if func_node is None:
        if isinstance(tree, ast.Module) and len(tree.body) == 1:
            n = tree.body[0]
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_node = n

    if func_node is None:
        return []

    orm_calls = _extract_orm_calls(func_node)
    return list(orm_calls)


def _extract_orm_calls(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, str]]:
    """Extract ORM-style calls from an AST function."""
    calls: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if _is_orm_call(node):
                call_str = _call_to_string(node)
                if call_str not in seen:
                    seen.add(call_str)
                    model = _extract_orm_model(node)
                    calls.append({"call": call_str, "detail": model})

    return calls


# ---------------------------------------------------------------------------
# Response tracing
# ---------------------------------------------------------------------------


def _trace_response(root: TraceNode, match: RouteMatch) -> None:
    """Add response information."""
    resp_detail: list[str] = []

    if match.response_model and match.response_model is not type(None):
        name = getattr(match.response_model, "__name__", str(match.response_model))
        resp_detail.append(name)

    resp_detail.append(f"HTTP {match.status_code}")

    # Detect response format from middleware
    try:
        for mw in settings.MIDDLEWARE:
            if "orjson" in mw.lower() or "ujson" in mw.lower():
                resp_detail.append(mw.rsplit(".", 1)[-1].replace("Middleware", ""))
                break
    except Exception:
        pass

    label = "JSON response"
    if resp_detail:
        label = f"JSON response ({', '.join(resp_detail)})"

    root.add_child(TraceNode(label=label))


# ---------------------------------------------------------------------------
# Dependency detection
# ---------------------------------------------------------------------------


def _trace_dependencies(root: TraceNode, match: RouteMatch) -> None:
    """Detect and report external dependencies."""
    deps: dict[str, str] = {}

    # Scan source code for known dependency patterns
    sources = [match.source_code]
    if match.controller_class:
        try:
            sources.append(inspect.getsource(match.controller_class))
        except (OSError, TypeError):
            pass

    for src in sources:
        if not src:
            continue
        for pattern, label, detail in _DEPENDENCY_PATTERNS:
            if pattern.lower() in src.lower():
                if label not in deps:
                    deps[label] = detail

    # Also check middleware for billing/email patterns
    try:
        for mw_path in settings.MIDDLEWARE:
            for pattern, label, detail in _DEPENDENCY_PATTERNS:
                if pattern.lower() in mw_path.lower():
                    if label not in deps:
                        deps[label] = detail
    except Exception:
        pass

    if deps:
        dep_lines = [f"{label}: {detail}" for label, detail in deps.items()]
        dep_node = TraceNode(label="Dependencies", detail=", ".join(dep_lines))
        root.add_child(dep_node)
