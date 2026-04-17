"""
File handling for django-matt.

Provides a complete file handling system with:
- File upload handling with validation
- Multiple storage backends (Local, S3, R2, MinIO, DO Spaces, Backblaze B2)
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

# Chunked/resumable uploads
from .chunked import (
    S3MultipartHandler,
    TusUploadHandler,
    TusUploadView,
    UploadSession,
)
from .config import (
    FileConfig,
    get_file_config,
    get_storage,
)

# Storage events
from .events import (
    FileEvent,
    emit_file_event,
    file_accessed,
    file_copied,
    file_deleted,
    file_moved,
    file_processed,
    file_uploaded,
)
from .local import LocalStorage

# File metadata extraction
from .metadata import (
    FileMetadata,
    extract_metadata,
)

# Presigned URLs
from .presigned import (
    PresignedUpload,
    generate_presigned_download,
    generate_presigned_upload,
)

# Image processing
from .processing import (
    ImageProcessor,
    ProcessedImage,
    process_image,
)
from .s3 import (
    B2Storage,
    DOSpacesStorage,
    MinIOStorage,
    R2Storage,
    S3Storage,
)
from .storage import (
    BaseStorage,
    StorageError,
)
from .storage import (
    FileNotFoundError as StorageFileNotFoundError,
)
from .upload import (
    MultipartParser,
    UploadedFile,
    get_uploaded_files,
    parse_multipart,
)
from .utils import (
    generate_unique_filename,
    get_content_type,
    get_file_extension,
    human_readable_size,
    sanitize_filename,
)
from .validators import (
    FileTooLargeError,
    FileValidator,
    InvalidExtensionError,
    InvalidFileTypeError,
    ValidationError,
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
    "B2Storage",
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
    # Chunked/resumable uploads
    "TusUploadHandler",
    "TusUploadView",
    "S3MultipartHandler",
    "UploadSession",
    # Presigned URLs
    "PresignedUpload",
    "generate_presigned_upload",
    "generate_presigned_download",
    # Image processing
    "ImageProcessor",
    "ProcessedImage",
    "process_image",
    # File metadata
    "FileMetadata",
    "extract_metadata",
    # Storage events
    "FileEvent",
    "emit_file_event",
    "file_uploaded",
    "file_deleted",
    "file_accessed",
    "file_moved",
    "file_copied",
    "file_processed",
]
