"""Tests for Rust middleware chain and query builder."""

from __future__ import annotations

import pytest

from django_matt._accel import (
    HAS_RUST,
    MiddlewareChainRust,
    build_filter_clause_rust,
    build_select_rust,
)

pytestmark = pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not compiled")


class TestMiddlewareChain:
    def test_cors_layer(self):
        chain = MiddlewareChainRust()
        chain.add_rust_layer("cors", '{"type": "cors", "allow_origin": "*"}')
        result = chain.process({"Host": "example.com"})
        assert result.action == "continue"
        assert result.headers["Access-Control-Allow-Origin"] == "*"

    def test_header_injection(self):
        chain = MiddlewareChainRust()
        chain.add_rust_layer("sec", '{"type": "headers", "X-Frame-Options": "DENY", "X-XSS-Protection": "1"}')
        result = chain.process({})
        assert result.headers["X-Frame-Options"] == "DENY"
        assert result.headers["X-XSS-Protection"] == "1"

    def test_block_layer(self):
        chain = MiddlewareChainRust()
        chain.add_rust_layer("blocker", '{"type": "block", "if_header": "X-Bad", "equals": "true"}')
        result = chain.process({"X-Bad": "true"})
        assert result.action == "block"

    def test_block_layer_no_match(self):
        chain = MiddlewareChainRust()
        chain.add_rust_layer("blocker", '{"type": "block", "if_header": "X-Bad", "equals": "true"}')
        result = chain.process({"X-Bad": "false"})
        assert result.action == "continue"

    def test_multiple_layers(self):
        chain = MiddlewareChainRust()
        chain.add_rust_layer("cors", '{"type": "cors", "allow_origin": "https://app.com"}')
        chain.add_rust_layer("headers", '{"type": "headers", "X-Custom": "val"}')
        result = chain.process({})
        assert result.headers["Access-Control-Allow-Origin"] == "https://app.com"
        assert result.headers["X-Custom"] == "val"

    def test_layer_count(self):
        chain = MiddlewareChainRust()
        assert chain.layer_count == 0
        chain.add_rust_layer("a", '{"type": "headers"}')
        chain.add_rust_layer("b", '{"type": "headers"}')
        assert chain.layer_count == 2

    def test_layer_names(self):
        chain = MiddlewareChainRust()
        chain.add_rust_layer("cors", '{"type": "cors"}')
        chain.add_rust_layer("sec", '{"type": "headers"}')
        assert chain.layer_names() == ["cors", "sec"]

    def test_invalid_config_json(self):
        chain = MiddlewareChainRust()
        with pytest.raises(ValueError, match="Invalid config JSON"):
            chain.add_rust_layer("bad", "not json")

    def test_block_stops_chain(self):
        chain = MiddlewareChainRust()
        chain.add_rust_layer("blocker", '{"type": "block", "if_header": "X-Bad", "equals": "yes"}')
        chain.add_rust_layer("headers", '{"type": "headers", "X-After": "should-not-appear"}')
        result = chain.process({"X-Bad": "yes"})
        assert result.action == "block"
        assert "X-After" not in result.headers


class TestBuildSelect:
    def test_basic_select(self):
        sql, params = build_select_rust(
            "users", ["id", "name"], [], [], None, None
        )
        assert sql == 'SELECT "id", "name" FROM "users"'
        assert params == []

    def test_select_star(self):
        sql, params = build_select_rust("users", [], [], [], None, None)
        assert "SELECT *" in sql

    def test_with_filters(self):
        sql, params = build_select_rust(
            "users", ["id"], [("age", "gte", "18")], [], None, None
        )
        assert "WHERE" in sql
        assert '"age" >=' in sql
        assert params == ["18"]

    def test_with_order_by(self):
        sql, _ = build_select_rust(
            "users", ["id"], [], [("name", False), ("age", True)], None, None
        )
        assert '"name" ASC' in sql
        assert '"age" DESC' in sql

    def test_with_limit_offset(self):
        sql, _ = build_select_rust("users", ["id"], [], [], 10, 20)
        assert "LIMIT 10" in sql
        assert "OFFSET 20" in sql

    def test_zero_offset_omitted(self):
        sql, _ = build_select_rust("users", ["id"], [], [], 10, 0)
        assert "OFFSET" not in sql

    def test_full_query(self):
        sql, params = build_select_rust(
            "products",
            ["id", "name", "price"],
            [("price", "gte", "10"), ("category", "eq", "electronics")],
            [("price", True)],
            25,
            50,
        )
        assert 'SELECT "id", "name", "price"' in sql
        assert 'FROM "products"' in sql
        assert "WHERE" in sql
        assert "ORDER BY" in sql
        assert "LIMIT 25" in sql
        assert "OFFSET 50" in sql
        assert len(params) == 2


class TestBuildFilterClause:
    def test_eq(self):
        clause, params = build_filter_clause_rust([("name", "eq", "Matt")])
        assert '"name" = $1' in clause
        assert params == ["Matt"]

    def test_in_operator(self):
        clause, params = build_filter_clause_rust([("role", "in", "admin,editor,viewer")])
        assert "IN" in clause
        assert len(params) == 3

    def test_is_null(self):
        clause, params = build_filter_clause_rust([("deleted_at", "is_null", "true")])
        assert "IS NULL" in clause
        assert params == []

    def test_is_not_null(self):
        clause, params = build_filter_clause_rust([("deleted_at", "is_null", "false")])
        assert "IS NOT NULL" in clause

    def test_multiple_filters(self):
        clause, params = build_filter_clause_rust([
            ("age", "gte", "18"),
            ("status", "eq", "active"),
        ])
        assert "AND" in clause
        assert len(params) == 2

    def test_unknown_operator(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            build_filter_clause_rust([("x", "bogus", "y")])

    def test_like(self):
        clause, params = build_filter_clause_rust([("name", "like", "%Matt%")])
        assert "LIKE" in clause
        assert params == ["%Matt%"]
