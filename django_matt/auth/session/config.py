"""
Session configuration.

Provides configuration for session authentication.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SessionConfig:
    """
    Configuration for session authentication.

    Can be loaded from Django settings or created directly.
    """

    # Session cookie settings
    cookie_name: str = "sessionid"
    cookie_age: int = 86400 * 14  # 14 days in seconds
    cookie_domain: Optional[str] = None
    cookie_path: str = "/"
    cookie_secure: bool = True  # Require HTTPS
    cookie_httponly: bool = True  # Not accessible via JavaScript
    cookie_samesite: str = "Lax"  # "Strict", "Lax", or "None"

    # CSRF settings
    csrf_enabled: bool = True
    csrf_cookie_name: str = "csrftoken"
    csrf_cookie_age: int = 86400 * 365  # 1 year
    csrf_cookie_secure: bool = True
    csrf_cookie_httponly: bool = False  # JS needs access for AJAX
    csrf_cookie_samesite: str = "Lax"
    csrf_header_name: str = "X-CSRFToken"
    csrf_trusted_origins: List[str] = field(default_factory=list)

    # Session behavior
    session_engine: str = "django.contrib.sessions.backends.db"
    session_save_every_request: bool = False
    session_expire_at_browser_close: bool = False

    # Security settings
    rotate_session_on_login: bool = True  # Prevent session fixation
    clear_session_on_logout: bool = True
    single_session_per_user: bool = False  # Only one active session
    track_session_activity: bool = True  # Track last activity time

    # Fresh session (for sensitive operations)
    fresh_session_duration: int = 300  # 5 minutes

    # Session data limits
    max_session_data_size: int = 4096  # 4KB

    @classmethod
    def from_django_settings(cls) -> "SessionConfig":
        """
        Load configuration from Django settings.

        Looks for DJANGO_MATT_SESSION dict in settings.
        """
        try:
            from django.conf import settings

            config_dict = getattr(settings, "DJANGO_MATT_SESSION", {})

            # Also check standard Django session settings
            django_session = {
                "cookie_name": getattr(settings, "SESSION_COOKIE_NAME", "sessionid"),
                "cookie_age": getattr(settings, "SESSION_COOKIE_AGE", 86400 * 14),
                "cookie_domain": getattr(settings, "SESSION_COOKIE_DOMAIN", None),
                "cookie_path": getattr(settings, "SESSION_COOKIE_PATH", "/"),
                "cookie_secure": getattr(settings, "SESSION_COOKIE_SECURE", True),
                "cookie_httponly": getattr(settings, "SESSION_COOKIE_HTTPONLY", True),
                "cookie_samesite": getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
                "session_engine": getattr(
                    settings,
                    "SESSION_ENGINE",
                    "django.contrib.sessions.backends.db",
                ),
                "session_save_every_request": getattr(
                    settings, "SESSION_SAVE_EVERY_REQUEST", False
                ),
                "session_expire_at_browser_close": getattr(
                    settings, "SESSION_EXPIRE_AT_BROWSER_CLOSE", False
                ),
            }

            # Django CSRF settings
            csrf_settings = {
                "csrf_cookie_name": getattr(settings, "CSRF_COOKIE_NAME", "csrftoken"),
                "csrf_cookie_age": getattr(settings, "CSRF_COOKIE_AGE", 86400 * 365),
                "csrf_cookie_secure": getattr(settings, "CSRF_COOKIE_SECURE", True),
                "csrf_cookie_httponly": getattr(settings, "CSRF_COOKIE_HTTPONLY", False),
                "csrf_cookie_samesite": getattr(settings, "CSRF_COOKIE_SAMESITE", "Lax"),
                "csrf_header_name": getattr(
                    settings, "CSRF_HEADER_NAME", "HTTP_X_CSRFTOKEN"
                ).replace("HTTP_", "").replace("_", "-"),
                "csrf_trusted_origins": getattr(settings, "CSRF_TRUSTED_ORIGINS", []),
            }

            # Merge settings (DJANGO_MATT_SESSION takes precedence)
            merged = {**django_session, **csrf_settings}

            # Convert DJANGO_MATT_SESSION keys to snake_case
            for key, value in config_dict.items():
                snake_key = key.lower()
                merged[snake_key] = value

        except Exception:
            merged = {}

        return cls(
            cookie_name=merged.get("cookie_name", "sessionid"),
            cookie_age=merged.get("cookie_age", 86400 * 14),
            cookie_domain=merged.get("cookie_domain"),
            cookie_path=merged.get("cookie_path", "/"),
            cookie_secure=merged.get("cookie_secure", True),
            cookie_httponly=merged.get("cookie_httponly", True),
            cookie_samesite=merged.get("cookie_samesite", "Lax"),
            csrf_enabled=merged.get("csrf_enabled", True),
            csrf_cookie_name=merged.get("csrf_cookie_name", "csrftoken"),
            csrf_cookie_age=merged.get("csrf_cookie_age", 86400 * 365),
            csrf_cookie_secure=merged.get("csrf_cookie_secure", True),
            csrf_cookie_httponly=merged.get("csrf_cookie_httponly", False),
            csrf_cookie_samesite=merged.get("csrf_cookie_samesite", "Lax"),
            csrf_header_name=merged.get("csrf_header_name", "X-CSRFToken"),
            csrf_trusted_origins=merged.get("csrf_trusted_origins", []),
            session_engine=merged.get(
                "session_engine", "django.contrib.sessions.backends.db"
            ),
            session_save_every_request=merged.get("session_save_every_request", False),
            session_expire_at_browser_close=merged.get(
                "session_expire_at_browser_close", False
            ),
            rotate_session_on_login=merged.get("rotate_session_on_login", True),
            clear_session_on_logout=merged.get("clear_session_on_logout", True),
            single_session_per_user=merged.get("single_session_per_user", False),
            track_session_activity=merged.get("track_session_activity", True),
            fresh_session_duration=merged.get("fresh_session_duration", 300),
            max_session_data_size=merged.get("max_session_data_size", 4096),
        )


# Global config instance
_config: Optional[SessionConfig] = None


def get_session_config() -> SessionConfig:
    """Get the global session configuration."""
    global _config
    if _config is None:
        _config = SessionConfig.from_django_settings()
    return _config


def set_session_config(config: SessionConfig) -> None:
    """Set the global session configuration."""
    global _config
    _config = config
