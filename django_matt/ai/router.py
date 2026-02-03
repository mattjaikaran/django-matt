"""
LLM Router for automatic failover, load balancing, and cost management.

Provides intelligent routing between multiple LLM providers with:
- Automatic failover on errors
- Load balancing across providers
- Cost tracking and limits
- Latency-based routing
"""

import asyncio
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    LLMProvider,
    Message,
    StreamChunk,
)

T = TypeVar("T", bound=BaseModel)


class RoutingStrategy(str, Enum):
    """Routing strategy for selecting providers."""

    FAILOVER = "failover"  # Primary first, then fallbacks
    ROUND_ROBIN = "round_robin"  # Cycle through providers
    RANDOM = "random"  # Random selection
    LOWEST_LATENCY = "lowest_latency"  # Prefer fastest provider
    LOWEST_COST = "lowest_cost"  # Prefer cheapest provider


@dataclass
class ProviderMetrics:
    """Metrics for a provider."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_latency: float = 0.0
    last_error: str | None = None
    last_error_time: float | None = None
    circuit_open: bool = False
    circuit_open_until: float | None = None


@dataclass
class ProviderConfig:
    """Configuration for a provider in the router."""

    provider: LLMProvider
    weight: float = 1.0
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    max_retries: int = 3
    timeout: float | None = None
    enabled: bool = True


@dataclass
class RouterConfig:
    """Configuration for the LLM router."""

    strategy: RoutingStrategy = RoutingStrategy.FAILOVER
    daily_cost_limit: float | None = None
    max_latency_ms: float | None = None
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    retry_delay: float = 0.5
    retry_backoff: float = 2.0


class LLMRouter:
    """
    Intelligent router for multiple LLM providers.

    Provides automatic failover, load balancing, and cost management
    across multiple providers.

    Usage:
        from django_matt.ai import LLMRouter, get_provider

        # Simple failover setup
        router = LLMRouter(
            primary="groq",  # Fast provider
            fallback=["anthropic", "openai"],  # Reliable fallbacks
        )
        response = await router.complete([Message.user("Hello!")])

        # Advanced configuration
        router = LLMRouter(
            providers={
                "groq": ProviderConfig(
                    provider=get_provider("groq"),
                    cost_per_1k_input=0.0001,
                    cost_per_1k_output=0.0002,
                ),
                "anthropic": ProviderConfig(
                    provider=get_provider("anthropic"),
                    cost_per_1k_input=0.003,
                    cost_per_1k_output=0.015,
                ),
            },
            config=RouterConfig(
                strategy=RoutingStrategy.LOWEST_COST,
                daily_cost_limit=10.0,
            ),
        )
    """

    def __init__(
        self,
        primary: str | LLMProvider | None = None,
        fallback: list[str | LLMProvider] | None = None,
        providers: dict[str, ProviderConfig] | None = None,
        config: RouterConfig | None = None,
    ):
        """
        Initialize the router.

        Args:
            primary: Primary provider (name or instance)
            fallback: List of fallback providers
            providers: Dict of provider configurations
            config: Router configuration
        """
        self.config = config or RouterConfig()
        self._providers: dict[str, ProviderConfig] = {}
        self._metrics: dict[str, ProviderMetrics] = {}
        self._round_robin_index = 0
        self._daily_cost = 0.0
        self._cost_reset_time = time.time()

        # Initialize from providers dict if provided
        if providers:
            for name, pconfig in providers.items():
                self._providers[name] = pconfig
                self._metrics[name] = ProviderMetrics()

        # Initialize from primary/fallback if provided
        elif primary is not None:
            self._init_from_simple_config(primary, fallback or [])

    def _init_from_simple_config(
        self,
        primary: str | LLMProvider,
        fallback: list[str | LLMProvider],
    ) -> None:
        """Initialize from simple primary/fallback configuration."""
        from django_matt.ai import get_provider

        # Add primary
        if isinstance(primary, str):
            provider = get_provider(primary)
            name = primary
        else:
            provider = primary
            name = provider.provider_name

        self._providers[name] = ProviderConfig(provider=provider, weight=2.0)
        self._metrics[name] = ProviderMetrics()

        # Add fallbacks
        for fb in fallback:
            if isinstance(fb, str):
                provider = get_provider(fb)
                name = fb
            else:
                provider = fb
                name = provider.provider_name

            self._providers[name] = ProviderConfig(provider=provider, weight=1.0)
            self._metrics[name] = ProviderMetrics()

    def _check_cost_limit(self) -> bool:
        """Check if daily cost limit has been reached."""
        if self.config.daily_cost_limit is None:
            return True

        # Reset cost counter daily
        current_time = time.time()
        if current_time - self._cost_reset_time > 86400:
            self._daily_cost = 0.0
            self._cost_reset_time = current_time

        return self._daily_cost < self.config.daily_cost_limit

    def _check_circuit_breaker(self, name: str) -> bool:
        """Check if circuit breaker allows requests."""
        metrics = self._metrics[name]

        if not metrics.circuit_open:
            return True

        # Check if circuit should be closed
        if metrics.circuit_open_until and time.time() > metrics.circuit_open_until:
            metrics.circuit_open = False
            metrics.circuit_open_until = None
            return True

        return False

    def _open_circuit(self, name: str) -> None:
        """Open circuit breaker for a provider."""
        metrics = self._metrics[name]
        metrics.circuit_open = True
        metrics.circuit_open_until = time.time() + self.config.circuit_breaker_timeout

    def _select_provider(self) -> list[str]:
        """Select providers based on routing strategy."""
        available = [
            name
            for name, config in self._providers.items()
            if config.enabled and self._check_circuit_breaker(name)
        ]

        if not available:
            # All circuits open, try primary anyway
            available = list(self._providers.keys())

        if self.config.strategy == RoutingStrategy.FAILOVER:
            # Return in order of weight (highest first)
            return sorted(
                available,
                key=lambda n: self._providers[n].weight,
                reverse=True,
            )

        elif self.config.strategy == RoutingStrategy.ROUND_ROBIN:
            # Rotate through providers
            rotated = available[self._round_robin_index :] + available[: self._round_robin_index]
            self._round_robin_index = (self._round_robin_index + 1) % len(available)
            return rotated

        elif self.config.strategy == RoutingStrategy.RANDOM:
            # Weighted random selection
            weights = [self._providers[n].weight for n in available]
            total = sum(weights)
            probs = [w / total for w in weights]
            selected = random.choices(available, weights=probs, k=len(available))
            return list(dict.fromkeys(selected))  # Remove duplicates while preserving order

        elif self.config.strategy == RoutingStrategy.LOWEST_LATENCY:
            # Sort by average latency
            def avg_latency(name: str) -> float:
                m = self._metrics[name]
                if m.successful_requests == 0:
                    return float("inf")
                return m.total_latency / m.successful_requests

            return sorted(available, key=avg_latency)

        elif self.config.strategy == RoutingStrategy.LOWEST_COST:
            # Sort by cost per token
            def cost(name: str) -> float:
                c = self._providers[name]
                return c.cost_per_1k_input + c.cost_per_1k_output

            return sorted(available, key=cost)

        return available

    def _calculate_cost(
        self,
        name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Calculate cost for a request."""
        config = self._providers[name]
        cost = (prompt_tokens / 1000) * config.cost_per_1k_input
        cost += (completion_tokens / 1000) * config.cost_per_1k_output
        return cost

    def _update_metrics(
        self,
        name: str,
        success: bool,
        latency: float,
        usage: Any | None = None,
        error: str | None = None,
    ) -> None:
        """Update metrics for a provider."""
        metrics = self._metrics[name]
        metrics.total_requests += 1
        metrics.total_latency += latency

        if success:
            metrics.successful_requests += 1
            if usage:
                metrics.total_tokens += usage.total_tokens
                cost = self._calculate_cost(
                    name,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                )
                metrics.total_cost += cost
                self._daily_cost += cost
        else:
            metrics.failed_requests += 1
            metrics.last_error = error
            metrics.last_error_time = time.time()

            # Check circuit breaker threshold
            if metrics.failed_requests >= self.config.circuit_breaker_threshold:
                self._open_circuit(name)

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate a completion using the router.

        Automatically handles failover and retry logic.
        """
        if not self._check_cost_limit():
            raise RuntimeError("Daily cost limit reached")

        providers = self._select_provider()
        last_error = None

        for provider_name in providers:
            config = self._providers[provider_name]
            provider = config.provider
            delay = self.config.retry_delay

            for attempt in range(config.max_retries):
                start_time = time.time()
                try:
                    response = await provider.complete(
                        messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )

                    latency = time.time() - start_time
                    self._update_metrics(
                        provider_name,
                        success=True,
                        latency=latency,
                        usage=response.usage,
                    )

                    return response

                except Exception as e:
                    latency = time.time() - start_time
                    last_error = str(e)
                    self._update_metrics(
                        provider_name,
                        success=False,
                        latency=latency,
                        error=last_error,
                    )

                    # Wait before retry with exponential backoff
                    if attempt < config.max_retries - 1:
                        await asyncio.sleep(delay)
                        delay *= self.config.retry_backoff

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion using the router.

        Only attempts the first available provider (no failover during stream).
        """
        if not self._check_cost_limit():
            raise RuntimeError("Daily cost limit reached")

        providers = self._select_provider()
        if not providers:
            raise RuntimeError("No providers available")

        provider_name = providers[0]
        config = self._providers[provider_name]
        provider = config.provider

        start_time = time.time()
        try:
            async for chunk in provider.stream(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield chunk

            latency = time.time() - start_time
            self._update_metrics(provider_name, success=True, latency=latency)

        except Exception as e:
            latency = time.time() - start_time
            self._update_metrics(
                provider_name,
                success=False,
                latency=latency,
                error=str(e),
            )
            raise

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        **kwargs,
    ) -> T:
        """Generate a structured response using the router."""
        if not self._check_cost_limit():
            raise RuntimeError("Daily cost limit reached")

        providers = self._select_provider()
        last_error = None

        for provider_name in providers:
            config = self._providers[provider_name]
            provider = config.provider

            # Check if provider supports structured output
            if not hasattr(provider, "complete_structured"):
                continue

            start_time = time.time()
            try:
                result = await provider.complete_structured(
                    messages,
                    response_model,
                    model=model,
                    temperature=temperature,
                    **kwargs,
                )

                latency = time.time() - start_time
                self._update_metrics(provider_name, success=True, latency=latency)

                return result

            except Exception as e:
                latency = time.time() - start_time
                last_error = str(e)
                self._update_metrics(
                    provider_name,
                    success=False,
                    latency=latency,
                    error=last_error,
                )

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    def get_metrics(self, name: str | None = None) -> dict[str, ProviderMetrics]:
        """Get metrics for providers."""
        if name:
            return {name: self._metrics[name]}
        return self._metrics.copy()

    def get_daily_cost(self) -> float:
        """Get total cost for today."""
        return self._daily_cost

    def reset_metrics(self, name: str | None = None) -> None:
        """Reset metrics for providers."""
        if name:
            self._metrics[name] = ProviderMetrics()
        else:
            for n in self._metrics:
                self._metrics[n] = ProviderMetrics()

    def enable_provider(self, name: str) -> None:
        """Enable a provider."""
        if name in self._providers:
            self._providers[name].enabled = True

    def disable_provider(self, name: str) -> None:
        """Disable a provider."""
        if name in self._providers:
            self._providers[name].enabled = False

    def add_provider(
        self,
        name: str,
        provider: LLMProvider,
        **kwargs,
    ) -> None:
        """Add a new provider to the router."""
        self._providers[name] = ProviderConfig(provider=provider, **kwargs)
        self._metrics[name] = ProviderMetrics()

    def remove_provider(self, name: str) -> None:
        """Remove a provider from the router."""
        self._providers.pop(name, None)
        self._metrics.pop(name, None)


__all__ = [
    "LLMRouter",
    "ProviderConfig",
    "ProviderMetrics",
    "RouterConfig",
    "RoutingStrategy",
]
