"""Bitfield permission evaluator with optional Rust acceleration.

Compiles permission expressions once at startup, then evaluates in
nanoseconds per request. Uses the Rust ``PermissionEvaluator`` when
available, otherwise falls back to a pure-Python implementation.

Usage::

    from django_matt.permissions.evaluator import BitfieldEvaluator

    evaluator = BitfieldEvaluator()

    # Define permission bits
    ADMIN = 1
    EDITOR = 2
    VIEWER = 4
    BANNED = 8

    # Compile expressions (returns expression ID)
    can_edit = evaluator.compile("1 & (2 | 4)")  # admin AND (editor OR viewer)
    not_banned = evaluator.compile("!8")

    # Evaluate against a user's permission bitfield
    user_perms = 0b0011  # admin + editor
    evaluator.evaluate(can_edit, user_perms)     # True
    evaluator.evaluate(not_banned, user_perms)   # True
"""

from __future__ import annotations

import re

from django_matt._accel import HAS_RUST, PermissionEvaluatorRust


class _PythonPermissionEvaluator:
    """Pure-Python permission evaluator — fallback when Rust is unavailable."""

    def __init__(self) -> None:
        self._expressions: list[_Expr] = []

    def compile(self, expression: str) -> int:
        expr = _parse_expression(expression)
        idx = len(self._expressions)
        self._expressions.append(expr)
        return idx

    def evaluate(self, expr_id: int, user_permissions: int) -> bool:
        if expr_id < 0 or expr_id >= len(self._expressions):
            raise ValueError(f"Unknown expression ID: {expr_id}")
        return self._expressions[expr_id].evaluate(user_permissions)

    def evaluate_many(self, expr_ids: list[int], user_permissions: int) -> list[bool]:
        return [self.evaluate(eid, user_permissions) for eid in expr_ids]

    @property
    def expression_count(self) -> int:
        return len(self._expressions)


# --- Expression tree (mirrors the Rust implementation) ---

class _Expr:
    def evaluate(self, user_perms: int) -> bool:
        raise NotImplementedError


class _Bit(_Expr):
    def __init__(self, mask: int) -> None:
        self.mask = mask

    def evaluate(self, user_perms: int) -> bool:
        return (user_perms & self.mask) == self.mask


class _All(_Expr):
    def __init__(self, exprs: list[_Expr]) -> None:
        self.exprs = exprs

    def evaluate(self, user_perms: int) -> bool:
        return all(e.evaluate(user_perms) for e in self.exprs)


class _Any(_Expr):
    def __init__(self, exprs: list[_Expr]) -> None:
        self.exprs = exprs

    def evaluate(self, user_perms: int) -> bool:
        return any(e.evaluate(user_perms) for e in self.exprs)


class _Not(_Expr):
    def __init__(self, expr: _Expr) -> None:
        self.expr = expr

    def evaluate(self, user_perms: int) -> bool:
        return not self.expr.evaluate(user_perms)


# --- Tokenizer + recursive descent parser ---

_TOKEN_RE = re.compile(r"\d+|[&|!()]")


def _tokenize(expression: str) -> list[str]:
    return _TOKEN_RE.findall(expression)


def _parse_expression(expression: str) -> _Expr:
    tokens = _tokenize(expression)
    if not tokens:
        raise ValueError("Empty expression")
    pos = [0]
    result = _parse_or(tokens, pos)
    if pos[0] < len(tokens):
        raise ValueError(f"Unexpected token: {tokens[pos[0]]}")
    return result


def _parse_or(tokens: list[str], pos: list[int]) -> _Expr:
    left = _parse_and(tokens, pos)
    while pos[0] < len(tokens) and tokens[pos[0]] == "|":
        pos[0] += 1
        right = _parse_and(tokens, pos)
        if isinstance(left, _Any):
            left.exprs.append(right)
        else:
            left = _Any([left, right])
    return left


def _parse_and(tokens: list[str], pos: list[int]) -> _Expr:
    left = _parse_unary(tokens, pos)
    while pos[0] < len(tokens) and tokens[pos[0]] == "&":
        pos[0] += 1
        right = _parse_unary(tokens, pos)
        if isinstance(left, _All):
            left.exprs.append(right)
        else:
            left = _All([left, right])
    return left


def _parse_unary(tokens: list[str], pos: list[int]) -> _Expr:
    if pos[0] < len(tokens) and tokens[pos[0]] == "!":
        pos[0] += 1
        return _Not(_parse_unary(tokens, pos))
    return _parse_atom(tokens, pos)


def _parse_atom(tokens: list[str], pos: list[int]) -> _Expr:
    if pos[0] >= len(tokens):
        raise ValueError("Unexpected end of expression")
    tok = tokens[pos[0]]
    if tok == "(":
        pos[0] += 1
        expr = _parse_or(tokens, pos)
        if pos[0] >= len(tokens) or tokens[pos[0]] != ")":
            raise ValueError("Expected closing ')'")
        pos[0] += 1
        return expr
    if tok.isdigit():
        pos[0] += 1
        return _Bit(int(tok))
    raise ValueError(f"Unexpected token: {tok}")


class BitfieldEvaluator:
    """Permission evaluator with Rust acceleration.

    Automatically uses the Rust ``PermissionEvaluator`` when compiled,
    falling back to a pure-Python implementation otherwise.
    """

    def __init__(self) -> None:
        if HAS_RUST and PermissionEvaluatorRust is not None:
            self._backend = PermissionEvaluatorRust()
            self._is_rust = True
        else:
            self._backend = _PythonPermissionEvaluator()
            self._is_rust = False

    @property
    def is_rust_accelerated(self) -> bool:
        return self._is_rust

    def compile(self, expression: str) -> int:
        """Compile a permission expression. Returns expression ID."""
        return self._backend.compile(expression)

    def evaluate(self, expr_id: int, user_permissions: int) -> bool:
        """Evaluate whether user_permissions satisfies the expression."""
        return self._backend.evaluate(expr_id, user_permissions)

    def evaluate_many(self, expr_ids: list[int], user_permissions: int) -> list[bool]:
        """Bulk-evaluate multiple expressions for one user."""
        return self._backend.evaluate_many(expr_ids, user_permissions)

    @property
    def expression_count(self) -> int:
        return self._backend.expression_count
