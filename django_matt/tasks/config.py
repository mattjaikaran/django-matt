"""
Task configuration.

Provides configuration management and backend factory.
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .backends import BaseBackend


@dataclass
class TaskConfig:
    """
    Configuration for the task system.

    Can be loaded from Django settings or created directly.
    """

    # Backend selection
    backend: str = "sync"  # "celery", "dramatiq", "django_q", "sync"

    # Celery settings
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Dramatiq settings
    dramatiq_broker: str = "redis"
    dramatiq_redis_url: str = "redis://localhost:6379/0"
    dramatiq_rabbitmq_url: str = "amqp://guest:guest@localhost:5672"
    dramatiq_result_backend: Optional[str] = None

    # Common settings
    default_queue: str = "default"
    default_retry: int = 3
    default_retry_delay: int = 60
    default_timeout: int = 300
    task_always_eager: bool = False  # Execute tasks synchronously

    @classmethod
    def from_django_settings(cls) -> "TaskConfig":
        """
        Load configuration from Django settings.

        Looks for DJANGO_MATT_TASKS dict in settings.
        """
        try:
            from django.conf import settings

            config_dict = getattr(settings, "DJANGO_MATT_TASKS", {})
        except Exception:
            config_dict = {}

        return cls(
            backend=config_dict.get("BACKEND", "sync"),
            # Celery
            celery_broker_url=config_dict.get(
                "CELERY_BROKER_URL", "redis://localhost:6379/0"
            ),
            celery_result_backend=config_dict.get(
                "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
            ),
            # Dramatiq
            dramatiq_broker=config_dict.get("DRAMATIQ_BROKER", "redis"),
            dramatiq_redis_url=config_dict.get(
                "DRAMATIQ_REDIS_URL", "redis://localhost:6379/0"
            ),
            dramatiq_rabbitmq_url=config_dict.get(
                "DRAMATIQ_RABBITMQ_URL", "amqp://guest:guest@localhost:5672"
            ),
            dramatiq_result_backend=config_dict.get("DRAMATIQ_RESULT_BACKEND"),
            # Common
            default_queue=config_dict.get("DEFAULT_QUEUE", "default"),
            default_retry=config_dict.get("DEFAULT_RETRY", 3),
            default_retry_delay=config_dict.get("DEFAULT_RETRY_DELAY", 60),
            default_timeout=config_dict.get("DEFAULT_TIMEOUT", 300),
            task_always_eager=config_dict.get("TASK_ALWAYS_EAGER", False),
        )


# Global config instance
_config: Optional[TaskConfig] = None
_backend: Optional["BaseBackend"] = None


def get_task_config() -> TaskConfig:
    """
    Get the global task configuration.

    Lazy-loads from Django settings on first access.
    """
    global _config
    if _config is None:
        _config = TaskConfig.from_django_settings()
    return _config


def set_task_config(config: TaskConfig) -> None:
    """
    Set the global task configuration.

    Useful for testing or programmatic configuration.
    """
    global _config, _backend
    _config = config
    _backend = None  # Reset backend


def get_backend() -> "BaseBackend":
    """
    Get the configured task backend.

    Returns:
        The configured backend instance
    """
    global _backend

    if _backend is not None:
        return _backend

    config = get_task_config()

    # Force sync if TASK_ALWAYS_EAGER is set
    if config.task_always_eager:
        from .backends import SyncBackend

        _backend = SyncBackend()
        return _backend

    backend_name = config.backend.lower()

    if backend_name == "celery":
        from .backends import CeleryBackend

        _backend = CeleryBackend(
            CELERY_BROKER_URL=config.celery_broker_url,
            CELERY_RESULT_BACKEND=config.celery_result_backend,
        )
    elif backend_name == "dramatiq":
        from .backends import DramatiqBackend

        _backend = DramatiqBackend(
            DRAMATIQ_BROKER=config.dramatiq_broker,
            DRAMATIQ_REDIS_URL=config.dramatiq_redis_url,
            DRAMATIQ_RABBITMQ_URL=config.dramatiq_rabbitmq_url,
            DRAMATIQ_RESULT_BACKEND=config.dramatiq_result_backend,
        )
    elif backend_name == "django_q":
        from .backends import DjangoQBackend

        _backend = DjangoQBackend()
    elif backend_name == "sync":
        from .backends import SyncBackend

        _backend = SyncBackend()
    else:
        raise ValueError(
            f"Unknown task backend: {backend_name}. "
            f"Supported: celery, dramatiq, django_q, sync"
        )

    return _backend


def set_backend(backend: "BaseBackend") -> None:
    """
    Set the global task backend.

    Useful for testing or programmatic configuration.
    """
    global _backend
    _backend = backend
