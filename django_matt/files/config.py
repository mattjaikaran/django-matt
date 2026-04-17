"""
File storage configuration.

Provides configuration management and storage factory.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .storage import BaseStorage


@dataclass
class FileConfig:
    """
    Configuration for file handling.

    Can be loaded from Django settings or created directly.
    """

    # Default storage backend
    default_storage: str = "local"  # "local", "s3", "r2", "minio", "spaces"

    # Local storage settings
    local_path: str = "/var/uploads"
    local_url_prefix: str = "/media"

    # S3/R2/MinIO/Spaces settings
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint: str | None = None
    s3_public_url: str | None = None

    # R2-specific
    r2_account_id: str = ""

    # B2-specific
    b2_application_key_id: str = ""
    b2_application_key: str = ""

    # Validation defaults
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list[str] = field(
        default_factory=lambda: ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"]
    )
    allowed_content_types: list[str] = field(default_factory=list)

    # Upload settings
    chunk_size: int = 8192
    generate_unique_names: bool = True

    @classmethod
    def from_django_settings(cls) -> "FileConfig":
        """
        Load configuration from Django settings.

        Looks for DJANGO_MATT_FILES dict in settings.
        """
        try:
            from django.conf import settings

            config_dict = getattr(settings, "DJANGO_MATT_FILES", {})
        except Exception:
            config_dict = {}

        return cls(
            default_storage=config_dict.get("DEFAULT_STORAGE", "local"),
            # Local
            local_path=config_dict.get("LOCAL_PATH", "/var/uploads"),
            local_url_prefix=config_dict.get("LOCAL_URL_PREFIX", "/media"),
            # S3
            s3_bucket=config_dict.get("S3_BUCKET", ""),
            s3_region=config_dict.get("S3_REGION", "us-east-1"),
            s3_access_key=config_dict.get("S3_ACCESS_KEY", ""),
            s3_secret_key=config_dict.get("S3_SECRET_KEY", ""),
            s3_endpoint=config_dict.get("S3_ENDPOINT"),
            s3_public_url=config_dict.get("S3_PUBLIC_URL"),
            # R2
            r2_account_id=config_dict.get("R2_ACCOUNT_ID", ""),
            # B2
            b2_application_key_id=config_dict.get("B2_APPLICATION_KEY_ID", ""),
            b2_application_key=config_dict.get("B2_APPLICATION_KEY", ""),
            # Validation
            max_file_size=config_dict.get("MAX_FILE_SIZE", 10 * 1024 * 1024),
            allowed_extensions=config_dict.get(
                "ALLOWED_EXTENSIONS",
                ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"],
            ),
            allowed_content_types=config_dict.get("ALLOWED_CONTENT_TYPES", []),
            # Upload
            chunk_size=config_dict.get("CHUNK_SIZE", 8192),
            generate_unique_names=config_dict.get("GENERATE_UNIQUE_NAMES", True),
        )


# Global config instance
_config: FileConfig | None = None


def get_file_config() -> FileConfig:
    """
    Get the global file configuration.

    Lazy-loads from Django settings on first access.
    """
    global _config
    if _config is None:
        _config = FileConfig.from_django_settings()
    return _config


def set_file_config(config: FileConfig) -> None:
    """
    Set the global file configuration.

    Useful for testing or programmatic configuration.
    """
    global _config
    _config = config


def get_storage(
    backend: str = None,
    **kwargs: Any,
) -> "BaseStorage":
    """
    Get a storage backend instance.

    Args:
        backend: Storage backend name ("local", "s3", "r2", "minio", "spaces")
                If not provided, uses default from config.
        **kwargs: Override configuration options

    Returns:
        Configured storage backend instance

    Example:
        # Use default from settings
        storage = get_storage()

        # Use specific backend
        storage = get_storage("s3", bucket="my-bucket")

        # Use local for development
        storage = get_storage("local", base_path="./uploads")
    """
    config = get_file_config()
    backend = backend or config.default_storage

    if backend == "local":
        from .local import LocalStorage

        return LocalStorage(
            base_path=kwargs.get("base_path", config.local_path),
            base_url=kwargs.get("base_url", config.local_url_prefix),
        )

    if backend == "s3":
        from .s3 import S3Storage

        return S3Storage(
            bucket=kwargs.get("bucket", config.s3_bucket),
            region=kwargs.get("region", config.s3_region),
            access_key=kwargs.get("access_key", config.s3_access_key),
            secret_key=kwargs.get("secret_key", config.s3_secret_key),
            endpoint=kwargs.get("endpoint", config.s3_endpoint),
            public_url=kwargs.get("public_url", config.s3_public_url),
        )

    if backend == "r2":
        from .s3 import R2Storage

        return R2Storage(
            bucket=kwargs.get("bucket", config.s3_bucket),
            account_id=kwargs.get("account_id", config.r2_account_id),
            access_key=kwargs.get("access_key", config.s3_access_key),
            secret_key=kwargs.get("secret_key", config.s3_secret_key),
            public_url=kwargs.get("public_url", config.s3_public_url),
        )

    if backend == "minio":
        from .s3 import MinIOStorage

        return MinIOStorage(
            bucket=kwargs.get("bucket", config.s3_bucket),
            endpoint=kwargs.get("endpoint", config.s3_endpoint or "http://localhost:9000"),
            access_key=kwargs.get("access_key", config.s3_access_key or "minioadmin"),
            secret_key=kwargs.get("secret_key", config.s3_secret_key or "minioadmin"),
            public_url=kwargs.get("public_url", config.s3_public_url),
        )

    if backend == "spaces":
        from .s3 import DOSpacesStorage

        return DOSpacesStorage(
            bucket=kwargs.get("bucket", config.s3_bucket),
            region=kwargs.get("region", config.s3_region),
            access_key=kwargs.get("access_key", config.s3_access_key),
            secret_key=kwargs.get("secret_key", config.s3_secret_key),
            public_url=kwargs.get("public_url", config.s3_public_url),
        )

    if backend == "b2":
        from .s3 import B2Storage

        return B2Storage(
            bucket=kwargs.get("bucket", config.s3_bucket),
            region=kwargs.get("region", config.s3_region),
            application_key_id=kwargs.get("application_key_id", config.b2_application_key_id),
            application_key=kwargs.get("application_key", config.b2_application_key),
            public_url=kwargs.get("public_url", config.s3_public_url),
        )

    raise ValueError(
        f"Unknown storage backend: {backend}. Supported: local, s3, r2, minio, spaces, b2"
    )
