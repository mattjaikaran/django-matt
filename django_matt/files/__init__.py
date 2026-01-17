"""
File handling for django-matt.

Provides a complete file handling system with:
- File upload handling with validation
- Multiple storage backends (Local, S3, R2, MinIO, DO Spaces)
- Pre-signed URL generation
- Async support

Quick Start:
    # 1. Configure storage backend
    from django_matt.files import get_storage, LocalStorage, S3Storage

    # Local storage (development)
    storage = LocalStorage(base_path="/uploads")

    # S3 storage (production)
    storage = S3Storage(
        bucket="my-bucket",
        region="us-east-1",
        access_key="...",
        secret_key="...",
    )

    # Or use settings-based configuration
    storage = get_storage()  # Uses DJANGO_MATT_FILES settings

    # 2. Upload files
    from django_matt.files import UploadedFile, FileValidator

    @api.post("/upload")
    async def upload_file(request):
        file = UploadedFile.from_request(request)

        # Validate
        validator = FileValidator(
            max_size=10 * 1024 * 1024,  # 10MB
            allowed_types=["image/jpeg", "image/png"],
        )
        validator.validate(file)

        # Save
        path = await storage.save(file, folder="images")
        url = storage.url(path)

        return {"path": path, "url": url}

    # 3. Generate pre-signed URLs
    upload_url = await storage.presigned_upload_url(
        key="uploads/photo.jpg",
        expires=3600,
        content_type="image/jpeg",
    )

    download_url = await storage.presigned_download_url(
        key="uploads/photo.jpg",
        expires=3600,
    )

Configuration (settings.py):
    DJANGO_MATT_FILES = {
        "DEFAULT_STORAGE": "s3",  # or "local", "r2", "minio", "spaces"

        # Local storage
        "LOCAL_PATH": "/var/uploads",
        "LOCAL_URL_PREFIX": "/media",

        # S3/R2/MinIO/Spaces
        "S3_BUCKET": "my-bucket",
        "S3_REGION": "us-east-1",
        "S3_ACCESS_KEY": "...",
        "S3_SECRET_KEY": "...",
        "S3_ENDPOINT": None,  # Custom endpoint for R2/MinIO
        "S3_PUBLIC_URL": None,  # Custom public URL

        # Validation defaults
        "MAX_FILE_SIZE": 10 * 1024 * 1024,  # 10MB
        "ALLOWED_EXTENSIONS": ["jpg", "jpeg", "png", "gif", "pdf"],
    }
"""

from .upload import (
    UploadedFile,
    MultipartParser,
    parse_multipart,
    get_uploaded_files,
)

from .validators import (
    FileValidator,
    ValidationError,
    FileTooLargeError,
    InvalidFileTypeError,
    InvalidExtensionError,
)

from .storage import (
    BaseStorage,
    StorageError,
    FileNotFoundError as StorageFileNotFoundError,
)

from .local import LocalStorage

from .s3 import (
    S3Storage,
    R2Storage,
    MinIOStorage,
    DOSpacesStorage,
)

from .config import (
    FileConfig,
    get_file_config,
    get_storage,
)

from .utils import (
    get_file_extension,
    get_content_type,
    generate_unique_filename,
    sanitize_filename,
    human_readable_size,
)

__all__ = [
    # Upload
    "UploadedFile",
    "MultipartParser",
    "parse_multipart",
    "get_uploaded_files",
    # Validators
    "FileValidator",
    "ValidationError",
    "FileTooLargeError",
    "InvalidFileTypeError",
    "InvalidExtensionError",
    # Storage base
    "BaseStorage",
    "StorageError",
    "StorageFileNotFoundError",
    # Storage backends
    "LocalStorage",
    "S3Storage",
    "R2Storage",
    "MinIOStorage",
    "DOSpacesStorage",
    # Config
    "FileConfig",
    "get_file_config",
    "get_storage",
    # Utils
    "get_file_extension",
    "get_content_type",
    "generate_unique_filename",
    "sanitize_filename",
    "human_readable_size",
]
