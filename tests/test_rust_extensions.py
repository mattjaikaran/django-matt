"""Tests for Rust-accelerated rate limiter and permission evaluator.

Tests both the Python wrappers (TokenBucketThrottle, BitfieldEvaluator) and
the bypass/disable mechanisms. Works whether Rust is compiled or not.
"""

from __future__ import annotations

import pytest
from django.test import RequestFactory

from django_matt._accel import HAS_RUST
from django_matt.permissions.evaluator import BitfieldEvaluator
from django_matt.throttling.token_bucket import (
    TokenBucketThrottle,
    bypass_throttle,
    disable_throttle,
    enable_throttle,
)


# ──────────────────────────────────────────────
# TokenBucketThrottle
# ──────────────────────────────────────────────


class TestTokenBucketThrottle:
    @pytest.fixture
    def factory(self):
        return RequestFactory()

    def test_allows_within_capacity(self, factory):
        throttle = TokenBucketThrottle(capacity=5, refill_per_second=0.0)
        for i in range(5):
            request = factory.get("/test", REMOTE_ADDR="1.2.3.4")
            allowed, remaining, _ = throttle.check(request)
            assert allowed, f"Request {i} should be allowed"
            assert remaining == 4 - i

    def test_denies_over_capacity(self, factory):
        throttle = TokenBucketThrottle(capacity=2, refill_per_second=0.0)
        request = factory.get("/test", REMOTE_ADDR="1.2.3.4")
        throttle.check(request)
        throttle.check(request)
        allowed, remaining, _ = throttle.check(request)
        assert not allowed
        assert remaining == 0

    def test_different_ips_independent(self, factory):
        throttle = TokenBucketThrottle(capacity=1, refill_per_second=0.0)
        r1 = factory.get("/test", REMOTE_ADDR="1.1.1.1")
        r2 = factory.get("/test", REMOTE_ADDR="2.2.2.2")

        assert throttle.check(r1)[0] is True
        assert throttle.check(r2)[0] is True
        assert throttle.check(r1)[0] is False  # exhausted

    def test_check_key_direct(self):
        throttle = TokenBucketThrottle(capacity=3, refill_per_second=0.0)
        assert throttle.check_key("user:42")[0] is True
        assert throttle.check_key(b"user:42")[0] is True
        assert throttle.check_key("user:42")[0] is True
        assert throttle.check_key("user:42")[0] is False

    def test_custom_key_func(self, factory):
        throttle = TokenBucketThrottle(
            capacity=1,
            refill_per_second=0.0,
            key_func=lambda r: r.META.get("HTTP_X_API_KEY", "anon"),
        )
        request = factory.get("/test", HTTP_X_API_KEY="key-abc")
        assert throttle.check(request)[0] is True
        assert throttle.check(request)[0] is False

    def test_cleanup(self):
        throttle = TokenBucketThrottle(capacity=10, refill_per_second=1.0)
        throttle.check_key("a")
        throttle.check_key("b")
        removed = throttle.cleanup(max_idle_seconds=0.0)
        assert isinstance(removed, int)

    def test_is_rust_accelerated_flag(self):
        throttle = TokenBucketThrottle(capacity=10, refill_per_second=1.0)
        assert throttle.is_rust_accelerated == HAS_RUST

    def test_xff_header_key(self, factory):
        throttle = TokenBucketThrottle(capacity=1, refill_per_second=0.0)
        request = factory.get(
            "/test",
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_FOR="9.9.9.9, 10.0.0.1",
        )
        allowed, _, _ = throttle.check(request)
        assert allowed
        assert throttle.check(request)[0] is False
        request2 = factory.get(
            "/test",
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_FOR="8.8.8.8",
        )
        assert throttle.check(request2)[0] is True


# ──────────────────────────────────────────────
# Throttle bypass for testing
# ──────────────────────────────────────────────


class TestThrottleBypass:
    @pytest.fixture
    def factory(self):
        return RequestFactory()

    def test_disabled_instance(self, factory):
        throttle = TokenBucketThrottle(capacity=1, refill_per_second=0.0, disabled=True)
        request = factory.get("/test", REMOTE_ADDR="1.2.3.4")
        for _ in range(100):
            allowed, remaining, reset = throttle.check(request)
            assert allowed
            assert remaining == 1
            assert reset == 0

    def test_bypass_context_manager(self, factory):
        throttle = TokenBucketThrottle(capacity=1, refill_per_second=0.0)
        request = factory.get("/test", REMOTE_ADDR="1.2.3.4")

        with bypass_throttle():
            for _ in range(100):
                assert throttle.check(request)[0] is True

        # Outside context — fresh throttle to avoid stale state
        throttle2 = TokenBucketThrottle(capacity=1, refill_per_second=0.0)
        assert throttle2.check(request)[0] is True
        assert throttle2.check(request)[0] is False

    def test_disable_enable_global(self, factory):
        throttle = TokenBucketThrottle(capacity=1, refill_per_second=0.0)
        request = factory.get("/test", REMOTE_ADDR="1.2.3.4")

        disable_throttle()
        try:
            for _ in range(50):
                assert throttle.check(request)[0] is True
        finally:
            enable_throttle()

    def test_check_key_also_bypassed(self):
        throttle = TokenBucketThrottle(capacity=1, refill_per_second=0.0, disabled=True)
        for _ in range(50):
            assert throttle.check_key("any-key")[0] is True

    def test_settings_testing_flag(self, factory, settings):
        settings.TESTING = True
        throttle = TokenBucketThrottle(capacity=1, refill_per_second=0.0)
        request = factory.get("/test", REMOTE_ADDR="1.2.3.4")
        for _ in range(50):
            assert throttle.check(request)[0] is True


# ──────────────────────────────────────────────
# BitfieldEvaluator
# ──────────────────────────────────────────────


class TestBitfieldEvaluator:
    def test_single_bit(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("4")
        assert ev.evaluate(expr, 0b0100) is True
        assert ev.evaluate(expr, 0b0010) is False

    def test_and(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("1 & 2")
        assert ev.evaluate(expr, 0b11) is True
        assert ev.evaluate(expr, 0b01) is False
        assert ev.evaluate(expr, 0b10) is False

    def test_or(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("1 | 2")
        assert ev.evaluate(expr, 0b01) is True
        assert ev.evaluate(expr, 0b10) is True
        assert ev.evaluate(expr, 0b11) is True
        assert ev.evaluate(expr, 0b00) is False

    def test_not(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("!1")
        assert ev.evaluate(expr, 0b00) is True
        assert ev.evaluate(expr, 0b10) is True
        assert ev.evaluate(expr, 0b01) is False

    def test_complex_grouped(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("1 & (2 | 4)")
        assert ev.evaluate(expr, 0b011) is True
        assert ev.evaluate(expr, 0b101) is True
        assert ev.evaluate(expr, 0b001) is False
        assert ev.evaluate(expr, 0b110) is False

    def test_not_banned(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("1 & !8")
        assert ev.evaluate(expr, 0b0001) is True
        assert ev.evaluate(expr, 0b1001) is False
        assert ev.evaluate(expr, 0b1000) is False

    def test_evaluate_many(self):
        ev = BitfieldEvaluator()
        e0 = ev.compile("1")
        e1 = ev.compile("2")
        e2 = ev.compile("4")
        results = ev.evaluate_many([e0, e1, e2], 0b011)
        assert results == [True, True, False]

    def test_invalid_expression(self):
        ev = BitfieldEvaluator()
        with pytest.raises((ValueError, Exception)):
            ev.compile("")

    def test_invalid_expr_id(self):
        ev = BitfieldEvaluator()
        with pytest.raises((ValueError, Exception)):
            ev.evaluate(999, 0b01)

    def test_expression_count(self):
        ev = BitfieldEvaluator()
        assert ev.expression_count == 0
        ev.compile("1")
        ev.compile("2")
        assert ev.expression_count == 2

    def test_is_rust_accelerated_flag(self):
        ev = BitfieldEvaluator()
        assert ev.is_rust_accelerated == HAS_RUST

    def test_triple_or(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("1 | 2 | 4")
        assert ev.evaluate(expr, 0b001) is True
        assert ev.evaluate(expr, 0b010) is True
        assert ev.evaluate(expr, 0b100) is True
        assert ev.evaluate(expr, 0b000) is False

    def test_triple_and(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("1 & 2 & 4")
        assert ev.evaluate(expr, 0b111) is True
        assert ev.evaluate(expr, 0b011) is False
        assert ev.evaluate(expr, 0b101) is False

    def test_nested_not_in_group(self):
        ev = BitfieldEvaluator()
        expr = ev.compile("(!1) | 2")
        assert ev.evaluate(expr, 0b00) is True
        assert ev.evaluate(expr, 0b10) is True
        assert ev.evaluate(expr, 0b01) is False
        assert ev.evaluate(expr, 0b11) is True
