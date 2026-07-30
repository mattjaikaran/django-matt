"""
Acceleration layer — dispatches to Rust extensions when available,
falls back to pure Python implementations otherwise.

Usage:
    from django_matt._accel import HAS_RUST, RadixRouter
    from django_matt._accel import jwt_encode_rust, jwt_decode_rust, jwt_verify_rust
    from django_matt._accel import serialize_dicts_to_json, build_camel_case_map
"""

from __future__ import annotations

from collections.abc import Callable

try:
    from django_matt._rust import HAS_RUST_EXTENSIONS as HAS_RUST
    from django_matt._rust import MiddlewareChain as MiddlewareChainRust
    from django_matt._rust import PermissionEvaluator as PermissionEvaluatorRust
    from django_matt._rust import (
        RadixRouter,
        ResponseCache,
        build_camel_case_map,
        parse_json_bytes,
        serialize_dict_to_json,
        serialize_dicts_to_json,
    )
    from django_matt._rust import RateLimiter as RateLimiterRust
    from django_matt._rust import SchemaValidator as SchemaValidatorRust
    from django_matt._rust import build_filter_clause as build_filter_clause_rust
    from django_matt._rust import build_select as build_select_rust
    from django_matt._rust import jwt_decode as jwt_decode_rust
    from django_matt._rust import jwt_encode as jwt_encode_rust
    from django_matt._rust import jwt_verify as jwt_verify_rust
    from django_matt._rust import parse_headers as parse_headers_rust
    from django_matt._rust import parse_query_string as parse_query_string_rust
except ImportError:
    HAS_RUST = False
    RadixRouter = None  # type: ignore[assignment, misc]
    jwt_encode_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    jwt_decode_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    jwt_verify_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    parse_query_string_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    parse_headers_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    serialize_dicts_to_json: Callable | None = None  # type: ignore[assignment, no-redef]
    serialize_dict_to_json: Callable | None = None  # type: ignore[assignment, no-redef]
    build_camel_case_map: Callable | None = None  # type: ignore[assignment, no-redef]
    RateLimiterRust = None  # type: ignore[assignment, misc]
    PermissionEvaluatorRust = None  # type: ignore[assignment, misc]
    SchemaValidatorRust = None  # type: ignore[assignment, misc]
    MiddlewareChainRust = None  # type: ignore[assignment, misc]
    build_select_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    build_filter_clause_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    parse_json_bytes: Callable | None = None  # type: ignore[assignment, no-redef]
    ResponseCache = None  # type: ignore[assignment, misc]

__all__ = [
    "HAS_RUST",
    "PermissionEvaluatorRust",
    "RadixRouter",
    "RateLimiterRust",
    "SchemaValidatorRust",
    "build_camel_case_map",
    "jwt_decode_rust",
    "jwt_encode_rust",
    "jwt_verify_rust",
    "parse_headers_rust",
    "parse_query_string_rust",
    "serialize_dict_to_json",
    "serialize_dicts_to_json",
    "MiddlewareChainRust",
    "build_select_rust",
    "build_filter_clause_rust",
    "parse_json_bytes",
    "ResponseCache",
]
