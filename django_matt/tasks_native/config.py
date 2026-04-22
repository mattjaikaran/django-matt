"""
Configuration for the native task engine.

Supports zero-config development and one-line production setup.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .backends.base import BaseNativeBackend

BackendType = Literal["auto", "native", "celery", "dramatiq", "django_q", "sync"]


@dataclass
class NativeTaskConfig:
    """
    Configuration for the native task engine.

    Zero-config for development:
        - No configuration needed, uses sync backend
        - Tasks execute immediately in the same process

    One-line production setup:
        MATT_TASKS = {
            "backend": "redis",
            "url": "redis://localhost:6379/0",
        }
    """

    # Backend configuration
    backend: BackendType = "auto"
    url: str | None = None

    # Connection settings
    redis_url: str = "redis://localhost:6379/0"
    postgres_url: str | None = None

    # Queue settings
    default_queue: str = "default"
    queues: list[str] = field(default_factory=lambda: ["default", "high", "low"])

    # Execution settings
    default_timeout: int = 300
    default_max_retries: int = 3
    default_retry_delay: float = 60.0

    # Result backend
    store_results: bool = True
    result_ttl: int = 86400  # 24 hours

    # Development mode
    always_eager: bool = False  # Execute tasks synchronously
    eager_propagate_errors: bool = True

    # Worker settings
    worker_concurrency: int = 4
    worker_prefetch: int = 4

    @classmethod
    def from_django_settings(cls) -> "NativeTaskConfig":
        """
        Load configuration from Django settings.

        Looks for MATT_TASKS dict in settings. Falls back to
        DJANGO_MATT_TASKS for backwards compatibility.
        """
        try:
            from django.conf import settings

            config_dict = getattr(settings, "MATT_TASKS", None)
            if config_dict is None:
                config_dict = getattr(settings, "DJANGO_MATT_TASKS", {})
        except Exception:
            config_dict = {}

        return cls._from_dict(config_dict)

    @classmethod
    def _from_dict(cls, config_dict: dict[str, Any]) -> "NativeTaskConfig":
        """Create config from dictionary."""
        backend = config_dict.get("backend", "auto")
        url = config_dict.get("url")

        # Handle shorthand backends
        if backend in ("redis", "postgres", "rabbitmq"):
            url = url or config_dict.get(f"{backend}_url")
            backend = "native" if _is_django_6() else "auto"

        return cls(
            backend=backend,
            url=url,
            redis_url=config_dict.get("redis_url", "redis://localhost:6379/0"),
            postgres_url=config_dict.get("postgres_url"),
            default_queue=config_dict.get("default_queue", "default"),
            queues=config_dict.get("queues", ["default", "high", "low"]),
            default_timeout=config_dict.get("default_timeout", 300),
            default_max_retries=config_dict.get("default_max_retries", 3),
            default_retry_delay=config_dict.get("default_retry_delay", 60.0),
            store_results=config_dict.get("store_results", True),
            result_ttl=config_dict.get("result_ttl", 86400),
            always_eager=config_dict.get("always_eager", False),
            eager_propagate_errors=config_dict.get("eager_propagate_errors", True),
            worker_concurrency=config_dict.get("worker_concurrency", 4),
            worker_prefetch=config_dict.get("worker_prefetch", 4),
        )


def _is_django_6() -> bool:
    """Check if Django 6.0+ is installed."""
    try:
        import django

        version = tuple(int(x) for x in django.__version__.split(".")[:2])
        return version >= (6, 0)
    except Exception:
        return False


def _has_celery() -> bool:
    """Check if Celery is installed."""
    try:
        import celery  # noqa: F401

        return True
    except ImportError:
        return False


def _has_dramatiq() -> bool:
    """Check if Dramatiq is installed."""
    try:
        import dramatiq  # noqa: F401

        return True
    except ImportError:
        return False


def _has_django_q() -> bool:
    """Check if Django-Q2 is installed."""
    try:
        import django_q  # noqa: F401

        return True
    except ImportError:
        return False


# Global config instance
_config: NativeTaskConfig | None = None
_backend: "BaseNativeBackend | None" = None


def get_config() -> NativeTaskConfig:
    """Get the global task configuration (lazy-loads from Django settings)."""
    global _config
    if _config is None:
        _config = NativeTaskConfig.from_django_settings()
    return _config


def set_config(config: NativeTaskConfig) -> None:
    """Set the global task configuration."""
    global _config, _backend
    _config = config
    _backend = None


def get_backend() -> "BaseNativeBackend":
    """
    Get the configured task backend.

    Auto-detection order:
    1. Django 6.0+ native tasks (if available)
    2. Celery (if installed and configured)
    3. Dramatiq (if installed and configured)
    4. Django-Q2 (if installed)
    5. Sync backend (development fallback)
    """
    global _backend

    if _backend is not None:
        return _backend

    config = get_config()

    # Force sync if always_eager
    if config.always_eager:
        from .backends.sync import SyncNativeBackend

        _backend = SyncNativeBackend(config)
        return _backend

    backend_type = config.backend

    if backend_type == "auto":
        _backend = _auto_detect_backend(config)
    elif backend_type == "native":
        from .backends.django_native import DjangoNativeBackend

        _backend = DjangoNativeBackend(config)
    elif backend_type == "celery":
        from .backends.celery_compat import CeleryNativeBackend

        _backend = CeleryNativeBackend(config)
    elif backend_type == "dramatiq":
        from .backends.dramatiq_compat import DramatiqNativeBackend

        _backend = DramatiqNativeBackend(config)
    elif backend_type == "django_q":
        from .backends.django_q_compat import DjangoQNativeBackend

        _backend = DjangoQNativeBackend(config)
    elif backend_type == "sync":
        from .backends.sync import SyncNativeBackend

        _backend = SyncNativeBackend(config)
    else:
        raise ValueError(
            f"Unknown backend: {backend_type}. "
            f"Supported: auto, native, celery, dramatiq, django_q, sync"
        )

    return _backend


def _auto_detect_backend(config: NativeTaskConfig) -> "BaseNativeBackend":
    """Auto-detect the best available backend."""
    # Prefer Django 6.0 native tasks
    if _is_django_6():
        from .backends.django_native import DjangoNativeBackend

        return DjangoNativeBackend(config)

    # Fall back to existing task libraries
    if _has_celery():
        from .backends.celery_compat import CeleryNativeBackend

        return CeleryNativeBackend(config)

    if _has_dramatiq():
        from .backends.dramatiq_compat import DramatiqNativeBackend

        return DramatiqNativeBackend(config)

    if _has_django_q():
        from .backends.django_q_compat import DjangoQNativeBackend

        return DjangoQNativeBackend(config)

    # Development fallback: sync execution
    from .backends.sync import SyncNativeBackend

    return SyncNativeBackend(config)


def set_backend(backend: "BaseNativeBackend") -> None:
    """Set the global task backend (useful for testing)."""
    global _backend
    _backend = backend


def reset() -> None:
    """Reset global config and backend (useful for testing)."""
    global _config, _backend
    _config = None
    _backend = None
