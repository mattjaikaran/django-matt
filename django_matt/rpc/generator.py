"""Code generators that produce typed Python and TypeScript RPC clients from API routes."""

from __future__ import annotations

import inspect
import re
from typing import Any, get_type_hints

from pydantic import BaseModel


def _python_type_str(annotation: Any) -> str:
    if annotation is None or annotation is inspect.Parameter.empty:
        return "Any"
    if annotation is type(None):
        return "None"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        arg_strs = ", ".join(_python_type_str(a) for a in args)
        origin_name = getattr(origin, "__name__", str(origin))
        return f"{origin_name}[{arg_strs}]" if args else origin_name
    return str(annotation)


def _ts_type_str(annotation: Any) -> str:
    if annotation is None or annotation is inspect.Parameter.empty:
        return "any"
    if annotation is str:
        return "string"
    if annotation is int or annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is type(None):
        return "null"
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        args = getattr(annotation, "__args__", ())
        inner = _ts_type_str(args[0]) if args else "any"
        return f"{inner}[]"
    if origin is dict:
        args = getattr(annotation, "__args__", ())
        k = _ts_type_str(args[0]) if args else "string"
        v = _ts_type_str(args[1]) if len(args) > 1 else "any"
        return f"Record<{k}, {v}>"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return "any"


def _extract_routes(api: Any) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []

    for route in getattr(api, "routes", []):
        endpoint = route.get("endpoint")
        hints = {}
        if endpoint:
            try:
                hints = get_type_hints(endpoint)
            except Exception:
                hints = {}
        routes.append(
            {
                "name": route.get("name", "unknown"),
                "path": route.get("path", "/"),
                "methods": route.get("methods", ["GET"]),
                "response_model": route.get("response_model"),
                "hints": hints,
                "endpoint": endpoint,
            }
        )

    for controller_cls in getattr(api, "controllers", []):
        prefix = getattr(controller_cls, "prefix", "")
        for attr_name in dir(controller_cls):
            if attr_name.startswith("_"):
                continue
            method = getattr(controller_cls, attr_name, None)
            if method is None or not callable(method):
                continue
            route_info = getattr(method, "_route_info", None)
            if route_info is None:
                continue
            try:
                hints = get_type_hints(method)
            except Exception:
                hints = {}
            routes.append(
                {
                    "name": attr_name,
                    "path": prefix + route_info["path"],
                    "methods": route_info["methods"],
                    "response_model": route_info.get("response_model"),
                    "hints": hints,
                    "endpoint": method,
                    "controller": controller_cls.__name__,
                }
            )

    return routes


def _path_to_url_template(path: str) -> str:
    path = re.sub(r"<\w+:(\w+)>", r"{\1}", path)
    path = re.sub(r"<(\w+)>", r"{\1}", path)
    return path


def _extract_path_params(path: str) -> list[str]:
    return re.findall(r"\{(\w+)\}", _path_to_url_template(path))


def generate_python_client(api: Any, class_name: str = "GeneratedClient") -> str:
    """Generate a Python async RPC client class from an API's route definitions."""
    routes = _extract_routes(api)
    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from pydantic import BaseModel",
        "",
        "from django_matt.rpc.auth import AuthStrategy",
        "from django_matt.rpc.client import RPCClient",
        "",
        "",
    ]

    # Collect schema imports
    schemas: set[str] = set()
    for route in routes:
        rm = route.get("response_model")
        if rm and hasattr(rm, "__name__"):
            schemas.add(rm.__name__)
        for param_name, param_type in route["hints"].items():
            if param_name in ("return", "self", "request"):
                continue
            if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                schemas.add(param_type.__name__)

    lines.append(f"class {class_name}:")
    lines.append("    def __init__(")
    lines.append("        self,")
    lines.append("        base_url: str,")
    lines.append("        auth: AuthStrategy | None = None,")
    lines.append("        **kwargs: Any,")
    lines.append("    ):")
    lines.append("        self._client = RPCClient(base_url, auth=auth, **kwargs)")
    lines.append("")

    for route in routes:
        method_name = route["name"]
        http_method = route["methods"][0]
        path_template = _path_to_url_template(route["path"])
        path_params = _extract_path_params(route["path"])
        response_model = route.get("response_model")
        hints = route.get("hints", {})

        # Build params
        params: list[str] = []
        for pp in path_params:
            params.append(f"{pp}: str")

        # Body param for POST/PUT/PATCH
        body_param: str | None = None
        if http_method in ("POST", "PUT", "PATCH"):
            for param_name, param_type in hints.items():
                if param_name in ("return", "self", "request"):
                    continue
                if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                    type_str = _python_type_str(param_type)
                    params.append(f"data: {type_str}")
                    body_param = "data"
                    break

        # Return type
        return_type = "Any"
        if response_model:
            return_type = _python_type_str(response_model)

        sig_params = ", ".join(["self"] + params)
        lines.append(f"    async def {method_name}({sig_params}) -> {return_type}:")

        # Build path with f-string
        if path_params:
            path_expr = f'f"{path_template}"'
        else:
            path_expr = f'"{path_template}"'

        rm_arg = f"response_model={_python_type_str(response_model)}" if response_model else ""
        data_arg = f"data={body_param}" if body_param else ""
        extra_args = ", ".join(filter(None, [data_arg, rm_arg]))
        if extra_args:
            extra_args = ", " + extra_args

        lines.append("        return await self._client.request(")
        lines.append(f'            "{http_method}", {path_expr}{extra_args}')
        lines.append("        )")
        lines.append("")

    lines.append("    async def close(self) -> None:")
    lines.append("        await self._client.close()")
    lines.append("")
    lines.append(f"    async def __aenter__(self) -> {class_name}:")
    lines.append("        return self")
    lines.append("")
    lines.append("    async def __aexit__(self, *args: Any) -> None:")
    lines.append("        await self.close()")

    return "\n".join(lines)


def generate_typescript_client(api: Any, class_name: str = "APIClient") -> str:
    """Generate a TypeScript fetch-based client class from an API's route definitions."""
    routes = _extract_routes(api)
    lines: list[str] = [
        "// Auto-generated by django_matt.rpc.generator",
        "// Do not edit manually",
        "",
    ]

    # Collect interfaces from response models
    interfaces: dict[str, type] = {}
    for route in routes:
        rm = route.get("response_model")
        if rm and hasattr(rm, "__name__") and isinstance(rm, type) and issubclass(rm, BaseModel):
            interfaces[rm.__name__] = rm
        for param_name, param_type in route["hints"].items():
            if param_name in ("return", "self", "request"):
                continue
            if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                interfaces[param_type.__name__] = param_type

    # Generate interfaces
    for name, model in interfaces.items():
        lines.append(f"export interface {name} {{")
        for field_name, field_info in model.model_fields.items():
            ts_type = _ts_type_str(field_info.annotation)
            optional = "?" if not field_info.is_required() else ""
            lines.append(f"  {field_name}{optional}: {ts_type};")
        lines.append("}")
        lines.append("")

    lines.append(f"export class {class_name} {{")
    lines.append("  private baseUrl: string;")
    lines.append("  private headers: Record<string, string>;")
    lines.append("")
    lines.append("  constructor(baseUrl: string, headers: Record<string, string> = {}) {")
    lines.append('    this.baseUrl = baseUrl.replace(/\\/$/, "");')
    lines.append("    this.headers = {")
    lines.append('      "Content-Type": "application/json",')
    lines.append("      ...headers,")
    lines.append("    };")
    lines.append("  }")
    lines.append("")

    # Private fetch helper
    lines.append("  private async request<T>(")
    lines.append("    method: string,")
    lines.append("    path: string,")
    lines.append("    body?: unknown,")
    lines.append("    params?: Record<string, string>,")
    lines.append("  ): Promise<T> {")
    lines.append("    const url = new URL(`${this.baseUrl}${path}`);")
    lines.append("    if (params) {")
    lines.append("      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));")
    lines.append("    }")
    lines.append("    const resp = await fetch(url.toString(), {")
    lines.append("      method,")
    lines.append("      headers: this.headers,")
    lines.append("      body: body ? JSON.stringify(body) : undefined,")
    lines.append("    });")
    lines.append("    if (!resp.ok) {")
    lines.append("      throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);")
    lines.append("    }")
    lines.append("    if (resp.status === 204) return undefined as T;")
    lines.append("    return resp.json();")
    lines.append("  }")
    lines.append("")

    for route in routes:
        method_name = _to_camel_case(route["name"])
        http_method = route["methods"][0]
        path_template = _path_to_url_template(route["path"])
        path_params = _extract_path_params(route["path"])
        response_model = route.get("response_model")
        hints = route.get("hints", {})

        # Build TS params
        ts_params: list[str] = []
        for pp in path_params:
            ts_params.append(f"{pp}: string")

        # Body param
        body_var: str | None = None
        if http_method in ("POST", "PUT", "PATCH"):
            for param_name, param_type in hints.items():
                if param_name in ("return", "self", "request"):
                    continue
                if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                    ts_type = param_type.__name__
                    ts_params.append(f"data: {ts_type}")
                    body_var = "data"
                    break

        return_ts = (
            response_model.__name__
            if response_model and hasattr(response_model, "__name__")
            else "any"
        )
        sig = ", ".join(ts_params)

        # Build path expression
        if path_params:
            path_expr = "`" + re.sub(r"\{(\w+)\}", r"${\1}", path_template) + "`"
        else:
            path_expr = f'"{path_template}"'

        body_arg = f", {body_var}" if body_var else ""
        lines.append(f"  async {method_name}({sig}): Promise<{return_ts}> {{")
        lines.append(
            f'    return this.request<{return_ts}>("{http_method}", {path_expr}{body_arg});'
        )
        lines.append("  }")
        lines.append("")

    lines.append("}")
    return "\n".join(lines)


def _to_camel_case(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
