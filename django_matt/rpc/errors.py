from __future__ import annotations

from typing import Any


class RPCError(Exception):
    def __init__(self, message: str, status_code: int = 500, detail: Any = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, status_code={self.status_code})"


class RPCConnectionError(RPCError):
    def __init__(self, message: str = "Connection failed", detail: Any = None):
        super().__init__(message, status_code=503, detail=detail)


class RPCValidationError(RPCError):
    def __init__(
        self,
        message: str = "Validation error",
        errors: list[dict[str, Any]] | None = None,
    ):
        self.errors = errors or []
        super().__init__(message, status_code=422, detail={"errors": self.errors})


class RPCTimeoutError(RPCError):
    def __init__(self, message: str = "Request timed out", detail: Any = None):
        super().__init__(message, status_code=504, detail=detail)


class RPCAuthError(RPCError):
    def __init__(self, message: str = "Authentication failed", detail: Any = None):
        super().__init__(message, status_code=401, detail=detail)


class RPCNotFoundError(RPCError):
    def __init__(self, message: str = "Not found", detail: Any = None):
        super().__init__(message, status_code=404, detail=detail)


def error_from_response(status_code: int, body: dict[str, Any] | None = None) -> RPCError:
    body = body or {}
    message = body.get("detail", body.get("message", f"HTTP {status_code}"))

    if status_code == 401:
        return RPCAuthError(message, detail=body)
    if status_code == 404:
        return RPCNotFoundError(message, detail=body)
    if status_code == 422:
        return RPCValidationError(message, errors=body.get("errors", []))
    if status_code == 504:
        return RPCTimeoutError(message, detail=body)
    return RPCError(message, status_code=status_code, detail=body)
