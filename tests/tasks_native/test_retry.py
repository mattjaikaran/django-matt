"""
Tests for the native task engine retry module.
"""

import pytest

from django_matt.tasks_native import (
    CompositePolicy,
    ExponentialBackoff,
    FixedDelay,
    LinearBackoff,
    NoRetry,
    RetryOnException,
    RetryState,
    retry,
)


class TestExponentialBackoff:
    """Tests for ExponentialBackoff policy."""

    def test_basic_delays(self):
        """Test exponential delay calculation."""
        policy = ExponentialBackoff(base_delay=1.0, multiplier=2.0, jitter=False)

        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 4.0
        assert policy.get_delay(4) == 8.0

    def test_max_delay_cap(self):
        """Test max delay is respected."""
        policy = ExponentialBackoff(base_delay=100.0, multiplier=2.0, max_delay=150.0, jitter=False)

        assert policy.get_delay(1) == 100.0
        assert policy.get_delay(2) == 150.0  # Capped
        assert policy.get_delay(3) == 150.0  # Capped

    def test_should_retry(self):
        """Test retry decision based on attempt count."""
        policy = ExponentialBackoff(max_retries=3)

        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is True
        assert policy.should_retry(4) is False

    def test_retry_on_specific_exceptions(self):
        """Test retry only on specific exceptions."""
        policy = ExponentialBackoff(
            max_retries=3,
            retry_on=[ConnectionError, TimeoutError],
        )

        assert policy.should_retry(1, ConnectionError()) is True
        assert policy.should_retry(1, TimeoutError()) is True
        assert policy.should_retry(1, ValueError()) is False

    def test_jitter_adds_variance(self):
        """Test that jitter adds variance to delays."""
        policy = ExponentialBackoff(base_delay=10.0, jitter=True, jitter_factor=0.1)

        delays = [policy.get_delay(1) for _ in range(100)]
        assert min(delays) < 10.0
        assert max(delays) > 9.0
        assert min(delays) >= 9.0  # Within jitter range


class TestLinearBackoff:
    """Tests for LinearBackoff policy."""

    def test_basic_delays(self):
        """Test linear delay calculation."""
        policy = LinearBackoff(delay=5.0, increment=5.0)

        assert policy.get_delay(1) == 5.0
        assert policy.get_delay(2) == 10.0
        assert policy.get_delay(3) == 15.0
        assert policy.get_delay(4) == 20.0

    def test_max_delay_cap(self):
        """Test max delay is respected."""
        policy = LinearBackoff(delay=50.0, increment=50.0, max_delay=100.0)

        assert policy.get_delay(1) == 50.0
        assert policy.get_delay(2) == 100.0  # Capped
        assert policy.get_delay(3) == 100.0  # Capped

    def test_should_retry(self):
        """Test retry decision."""
        policy = LinearBackoff(max_retries=2)

        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is False


class TestFixedDelay:
    """Tests for FixedDelay policy."""

    def test_constant_delay(self):
        """Test delay is always constant."""
        policy = FixedDelay(delay=30.0)

        assert policy.get_delay(1) == 30.0
        assert policy.get_delay(2) == 30.0
        assert policy.get_delay(3) == 30.0
        assert policy.get_delay(100) == 30.0

    def test_should_retry(self):
        """Test retry decision."""
        policy = FixedDelay(max_retries=3)

        assert policy.should_retry(1) is True
        assert policy.should_retry(3) is True
        assert policy.should_retry(4) is False


class TestNoRetry:
    """Tests for NoRetry policy."""

    def test_never_retries(self):
        """Test that it never retries."""
        policy = NoRetry()

        assert policy.should_retry(1) is False
        assert policy.should_retry(0) is False

    def test_zero_delay(self):
        """Test delay is always zero."""
        policy = NoRetry()

        assert policy.get_delay(1) == 0


class TestRetryOnException:
    """Tests for RetryOnException policy."""

    def test_only_specified_exceptions(self):
        """Test retry only on specified exceptions."""
        policy = RetryOnException(
            exceptions=[ConnectionError, OSError],
            max_retries=3,
        )

        assert policy.should_retry(1, ConnectionError()) is True
        assert policy.should_retry(1, OSError()) is True
        assert policy.should_retry(1, ValueError()) is False
        assert policy.should_retry(1, TypeError()) is False

    def test_no_exception_no_retry(self):
        """Test no retry when no exception provided."""
        policy = RetryOnException(exceptions=[ConnectionError])

        assert policy.should_retry(1, None) is False

    def test_fixed_delay(self):
        """Test fixed delay mode."""
        policy = RetryOnException(
            exceptions=[ConnectionError],
            delay=10.0,
            exponential=False,
        )

        assert policy.get_delay(1) == 10.0
        assert policy.get_delay(2) == 10.0

    def test_exponential_delay(self):
        """Test exponential delay mode."""
        policy = RetryOnException(
            exceptions=[ConnectionError],
            delay=5.0,
            exponential=True,
            multiplier=2.0,
        )

        assert policy.get_delay(1) == 5.0
        assert policy.get_delay(2) == 10.0
        assert policy.get_delay(3) == 20.0


class TestCompositePolicy:
    """Tests for CompositePolicy."""

    def test_any_policy_allows_retry(self):
        """Test retry if any policy allows."""
        policy = CompositePolicy(
            policies=[
                RetryOnException([ConnectionError], max_retries=5),
                RetryOnException([ValueError], max_retries=2),
            ]
        )

        assert policy.should_retry(1, ConnectionError()) is True
        assert policy.should_retry(1, ValueError()) is True
        assert policy.should_retry(1, TypeError()) is False


class TestRetryFactory:
    """Tests for retry factory functions."""

    def test_exponential_factory(self):
        """Test retry.exponential factory."""
        policy = retry.exponential(max_retries=5, base_delay=2.0)

        assert isinstance(policy, ExponentialBackoff)
        assert policy.max_retries == 5
        assert policy.base_delay == 2.0

    def test_linear_factory(self):
        """Test retry.linear factory."""
        policy = retry.linear(max_retries=3, delay=15.0)

        assert isinstance(policy, LinearBackoff)
        assert policy.max_retries == 3
        assert policy.delay == 15.0

    def test_fixed_factory(self):
        """Test retry.fixed factory."""
        policy = retry.fixed(delay=45.0, max_retries=2)

        assert isinstance(policy, FixedDelay)
        assert policy.delay == 45.0
        assert policy.max_retries == 2

    def test_none_factory(self):
        """Test retry.none factory."""
        policy = retry.none()

        assert isinstance(policy, NoRetry)

    def test_on_exception_factory(self):
        """Test retry.on_exception factory."""
        policy = retry.on_exception(
            [ConnectionError, TimeoutError],
            max_retries=4,
            delay=10.0,
        )

        assert isinstance(policy, RetryOnException)
        assert policy.max_retries == 4

    def test_composite_factory(self):
        """Test retry.composite factory."""
        policy = retry.composite(
            [
                retry.exponential(max_retries=3),
                retry.fixed(delay=60.0),
            ]
        )

        assert isinstance(policy, CompositePolicy)
        assert len(policy.policies) == 2


class TestRetryState:
    """Tests for RetryState."""

    def test_initial_state(self):
        """Test initial retry state."""
        policy = retry.exponential(max_retries=3)
        state = RetryState(policy)

        assert state.attempt == 0
        assert state.last_exception is None
        assert state.delays == []
        assert state.is_exhausted is False

    def test_record_attempt(self):
        """Test recording attempts."""
        policy = retry.exponential(max_retries=3)
        state = RetryState(policy)

        exc = ValueError("test")
        state.record_attempt(exc)

        assert state.attempt == 1
        assert state.last_exception is exc

    def test_should_retry_delegates_to_policy(self):
        """Test should_retry delegates to policy."""
        policy = retry.exponential(max_retries=2)
        state = RetryState(policy)

        state.record_attempt(ValueError())
        assert state.should_retry() is True

        state.record_attempt(ValueError())
        assert state.should_retry() is True

        state.record_attempt(ValueError())
        assert state.should_retry() is False

    def test_get_next_delay(self):
        """Test getting next delay."""
        policy = retry.exponential(max_retries=3, base_delay=5.0, jitter=False)
        state = RetryState(policy)

        state.record_attempt()
        assert state.get_next_delay() == 5.0

        state.record_attempt()
        assert state.get_next_delay() == 10.0

    def test_is_exhausted(self):
        """Test exhausted state."""
        policy = retry.fixed(max_retries=2)
        state = RetryState(policy)

        assert state.is_exhausted is False

        state.record_attempt()
        state.record_attempt()

        assert state.is_exhausted is True

    def test_total_delay(self):
        """Test total delay calculation."""
        policy = retry.fixed(delay=10.0, max_retries=5)
        state = RetryState(policy)

        state.record_attempt()
        state.record_attempt()
        state.record_attempt()

        # First attempt has no delay, so total = 10 + 10 = 20
        assert state.total_delay == 20.0
