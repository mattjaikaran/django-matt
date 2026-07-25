"""
Tests for the files module.

Tests cover:
- FileInfo dataclass
- StorageError / FileNotFoundError / FileExistsError exceptions
- PresignedUrl dataclass
- FileValidator (size, type, extension, factory methods)
- Validation errors (FileTooLargeError, InvalidFileTypeError, InvalidExtensionError)
- LocalStorage (save, get, delete, exists, info, url, presigned, verify_signature)
- S3Storage (mocked boto3)
- UploadedFile (from_bytes, extension, chunks, read/seek/tell)
- Utility functions (get_file_extension, get_content_type, sanitize_filename, etc.)
- FileConfig
"""

import io
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from django_matt.files.config import FileConfig
from django_matt.files.storage import (
    BaseStorage,
    FileInfo,
    PresignedUrl,
    StorageError,
)
from django_matt.files.storage import (
    FileExistsError as StorageFileExistsError,
)
from django_matt.files.storage import (
    FileNotFoundError as StorageFileNotFoundError,
)
from django_matt.files.upload import (
    MultipartParser,
    UploadedFile,
)
from django_matt.files.utils import (
    generate_unique_filename,
    get_content_type,
    get_file_extension,
    human_readable_size,
    is_audio,
    is_document,
    is_image,
    is_video,
    parse_size,
    sanitize_filename,
    split_filename,
)
from django_matt.files.validators import (
    FileTooLargeError,
    FileValidator,
    InvalidExtensionError,
    InvalidFileTypeError,
    ValidationError,
)

# ==============================================================================
# FileInfo
# ==============================================================================


class TestFileInfo:
    def test_basic_creation(self):
        info = FileInfo(
            key="uploads/photo.jpg",
            size=1024,
            content_type="image/jpeg",
        )
        assert info.key == "uploads/photo.jpg"
        assert info.size == 1024
        assert info.content_type == "image/jpeg"
        assert info.last_modified is None
        assert info.etag is None
        assert info.metadata == {}

    def test_metadata_default(self):
        info = FileInfo(key="a", size=0, content_type="text/plain")
        assert info.metadata == {}
        info.metadata["custom"] = "val"
        assert info.metadata["custom"] == "val"

    def test_with_all_fields(self):
        now = datetime.utcnow()
        info = FileInfo(
            key="k",
            size=2048,
            content_type="application/pdf",
            last_modified=now,
            etag="abc123",
            metadata={"author": "test"},
        )
        assert info.last_modified is now
        assert info.etag == "abc123"
        assert info.metadata["author"] == "test"


# ==============================================================================
# Storage Errors
# ==============================================================================


class TestStorageErrors:
    def test_storage_error(self):
        err = StorageError("something broke", code="custom")
        assert str(err) == "something broke"
        assert err.code == "custom"

    def test_file_not_found_error(self):
        err = StorageFileNotFoundError("missing.txt")
        assert "missing.txt" in str(err)
        assert err.code == "file_not_found"
        assert err.key == "missing.txt"

    def test_file_exists_error(self):
        err = StorageFileExistsError("exists.txt")
        assert "exists.txt" in str(err)
        assert err.code == "file_exists"


# ==============================================================================
# PresignedUrl
# ==============================================================================


class TestPresignedUrl:
    def test_defaults(self):
        now = datetime.utcnow()
        url = PresignedUrl(url="https://example.com/upload", expires_at=now)
        assert url.method == "GET"
        assert url.headers == {}
        assert url.fields == {}

    def test_custom_values(self):
        now = datetime.utcnow()
        url = PresignedUrl(
            url="https://s3.example.com",
            expires_at=now,
            method="POST",
            headers={"Content-Type": "image/jpeg"},
            fields={"key": "uploads/file.jpg"},
        )
        assert url.method == "POST"
        assert url.headers["Content-Type"] == "image/jpeg"
        assert url.fields["key"] == "uploads/file.jpg"


# ==============================================================================
# UploadedFile
# ==============================================================================


class TestUploadedFile:
    def test_from_bytes(self):
        data = b"hello world"
        f = UploadedFile.from_bytes(data, filename="test.txt", content_type="text/plain")
        assert f.filename == "test.txt"
        assert f.content_type == "text/plain"
        assert f.size == len(data)
        assert f.read() == data

    def test_extension(self):
        f = UploadedFile.from_bytes(b"", filename="photo.JPG")
        assert f.extension == "jpg"

    def test_extension_missing(self):
        f = UploadedFile.from_bytes(b"", filename="noext")
        assert f.extension == ""

    def test_seek_and_tell(self):
        data = b"0123456789"
        f = UploadedFile.from_bytes(data, filename="data.bin")
        f.seek(5)
        assert f.tell() == 5
        assert f.read() == b"56789"

    def test_chunks(self):
        data = b"A" * 100
        f = UploadedFile.from_bytes(data, filename="big.bin")
        chunks = list(f.chunks(chunk_size=30))
        assert len(chunks) == 4  # 30 + 30 + 30 + 10
        assert b"".join(chunks) == data

    def test_repr(self):
        f = UploadedFile.from_bytes(b"x" * 10, filename="r.txt", content_type="text/plain")
        r = repr(f)
        assert "r.txt" in r
        assert "10" in r


# ==============================================================================
# FileValidator
# ==============================================================================


class TestFileValidator:
    def _make_file(self, size=100, filename="test.txt", content_type="text/plain"):
        return UploadedFile.from_bytes(b"x" * size, filename=filename, content_type=content_type)

    def test_max_size_pass(self):
        validator = FileValidator(max_size=200)
        f = self._make_file(size=100)
        validator.validate(f)  # should not raise

    def test_max_size_fail(self):
        validator = FileValidator(max_size=50)
        f = self._make_file(size=100)
        with pytest.raises(FileTooLargeError):
            validator.validate(f)

    def test_min_size_fail(self):
        validator = FileValidator(min_size=200)
        f = self._make_file(size=100)
        with pytest.raises(ValidationError, match="below minimum"):
            validator.validate(f)

    def test_allowed_extensions_pass(self):
        validator = FileValidator(allowed_extensions=["txt", "pdf"])
        f = self._make_file(filename="doc.txt")
        validator.validate(f)

    def test_allowed_extensions_fail(self):
        validator = FileValidator(allowed_extensions=["pdf"])
        f = self._make_file(filename="doc.txt")
        with pytest.raises(InvalidExtensionError):
            validator.validate(f)

    def test_allowed_types_pass(self):
        validator = FileValidator(allowed_types=["text/plain", "text/csv"])
        f = self._make_file(content_type="text/plain")
        validator.validate(f)

    def test_allowed_types_fail(self):
        validator = FileValidator(allowed_types=["image/jpeg"])
        f = self._make_file(content_type="text/plain")
        with pytest.raises(InvalidFileTypeError):
            validator.validate(f)

    def test_wildcard_type(self):
        validator = FileValidator(allowed_types=["image/*"])
        f = self._make_file(content_type="image/png", filename="img.png")
        validator.validate(f)  # should pass

    def test_denied_extensions(self):
        validator = FileValidator(denied_extensions=["exe", "bat"])
        f = self._make_file(filename="virus.exe")
        with pytest.raises(InvalidExtensionError):
            validator.validate(f)

    def test_denied_types(self):
        validator = FileValidator(denied_types=["application/x-msdownload"])
        f = self._make_file(content_type="application/x-msdownload", filename="bad.exe")
        with pytest.raises(InvalidFileTypeError):
            validator.validate(f)

    def test_require_extension(self):
        validator = FileValidator(require_extension=True)
        f = self._make_file(filename="noext")
        with pytest.raises(ValidationError, match="must have an extension"):
            validator.validate(f)

    def test_images_factory(self):
        validator = FileValidator.images()
        assert validator.max_size == 10 * 1024 * 1024
        assert "image/jpeg" in validator.allowed_types
        f = self._make_file(content_type="image/jpeg", filename="photo.jpg", size=100)
        validator.validate(f)

    def test_documents_factory(self):
        validator = FileValidator.documents()
        assert validator.max_size == 50 * 1024 * 1024
        assert "application/pdf" in validator.allowed_types

    def test_videos_factory(self):
        validator = FileValidator.videos()
        assert validator.max_size == 500 * 1024 * 1024
        assert "video/mp4" in validator.allowed_types

    def test_audio_factory(self):
        validator = FileValidator.audio()
        assert validator.max_size == 100 * 1024 * 1024
        assert "audio/mpeg" in validator.allowed_types


# ==============================================================================
# Validation errors
# ==============================================================================


class TestValidationErrors:
    def test_file_too_large_error_message(self):
        err = FileTooLargeError(size=20 * 1024 * 1024, max_size=10 * 1024 * 1024)
        assert err.code == "file_too_large"
        assert err.size == 20 * 1024 * 1024
        assert err.max_size == 10 * 1024 * 1024
        assert "MB" in str(err)

    def test_invalid_file_type_error(self):
        err = InvalidFileTypeError("video/avi", ["image/jpeg", "image/png"])
        assert err.code == "invalid_file_type"
        assert err.content_type == "video/avi"

    def test_invalid_extension_error(self):
        err = InvalidExtensionError("exe", ["txt", "pdf"])
        assert err.code == "invalid_extension"
        assert err.extension == "exe"
        assert ".txt" in str(err)


# ==============================================================================
# Utility functions
# ==============================================================================


class TestUtilFunctions:
    def test_get_file_extension(self):
        assert get_file_extension("photo.JPG") == "jpg"
        assert get_file_extension("archive.tar.gz") == "gz"
        assert get_file_extension("noext") == ""

    def test_get_content_type(self):
        assert get_content_type("image.jpg") == "image/jpeg"
        assert get_content_type("doc.pdf") == "application/pdf"
        assert get_content_type("unknown.qzx") == "application/octet-stream"

    def test_generate_unique_filename(self):
        name = generate_unique_filename(filename="photo.jpg")
        assert name.endswith(".jpg")
        name2 = generate_unique_filename(filename="photo.jpg")
        assert name != name2

    def test_generate_unique_filename_with_prefix(self):
        name = generate_unique_filename(prefix="avatar", extension="png")
        assert name.startswith("avatar_")
        assert name.endswith(".png")

    def test_sanitize_filename(self):
        assert sanitize_filename("hello world.txt") == "hello_world.txt"
        # Slashes get replaced with underscores
        assert sanitize_filename("path/to/file.txt") == "path_to_file.txt"
        # Backslashes get replaced
        assert sanitize_filename("path\\to\\file.txt") == "path_to_file.txt"

    def test_sanitize_filename_max_length(self):
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50

    def test_human_readable_size(self):
        assert human_readable_size(500) == "500.0 B"
        assert human_readable_size(1024) == "1.0 KB"
        assert human_readable_size(1024 * 1024) == "1.0 MB"
        assert human_readable_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_parse_size(self):
        assert parse_size("10MB") == 10 * 1024 * 1024
        assert parse_size("1GB") == 1024**3
        assert parse_size("512KB") == 512 * 1024
        assert parse_size("100B") == 100

    def test_parse_size_invalid(self):
        with pytest.raises(ValueError):
            parse_size("invalid")

    def test_split_filename(self):
        assert split_filename("photo.jpg") == ("photo", "jpg")
        assert split_filename("noext") == ("noext", "")
        assert split_filename("archive.tar.gz") == ("archive.tar", "gz")

    def test_is_image(self):
        assert is_image("image/jpeg") is True
        assert is_image("image/png") is True
        assert is_image("text/plain") is False

    def test_is_video(self):
        assert is_video("video/mp4") is True
        assert is_video("image/jpeg") is False

    def test_is_audio(self):
        assert is_audio("audio/mpeg") is True
        assert is_audio("video/mp4") is False

    def test_is_document(self):
        assert is_document("application/pdf") is True
        assert is_document("text/plain") is True
        assert is_document("image/png") is False


# ==============================================================================
# LocalStorage (async tests)
# ==============================================================================


@pytest.mark.asyncio
class TestLocalStorage:
    @pytest.fixture(autouse=True)
    def setup_storage(self, tmp_path):
        from django_matt.files.local import LocalStorage

        self.storage = LocalStorage(
            base_path=str(tmp_path),
            base_url="/media",
            secret_key="test-secret-key",
        )
        self.tmp_path = tmp_path

    async def test_save_and_get(self):
        key = await self.storage.save(b"hello world", key="test.txt")
        assert key == "test.txt"
        content = await self.storage.get(key)
        assert content == b"hello world"

    async def test_save_with_folder(self):
        key = await self.storage.save(b"data", key="file.txt", folder="uploads")
        assert key == "uploads/file.txt"
        content = await self.storage.get(key)
        assert content == b"data"

    async def test_exists(self):
        await self.storage.save(b"data", key="exists.txt")
        assert await self.storage.exists("exists.txt") is True
        assert await self.storage.exists("nope.txt") is False

    async def test_delete(self):
        await self.storage.save(b"data", key="todelete.txt")
        await self.storage.delete("todelete.txt")
        assert await self.storage.exists("todelete.txt") is False

    async def test_delete_not_found(self):
        with pytest.raises(StorageFileNotFoundError):
            await self.storage.delete("nonexistent.txt")

    async def test_get_not_found(self):
        with pytest.raises(StorageFileNotFoundError):
            await self.storage.get("nonexistent.txt")

    async def test_info(self):
        await self.storage.save(b"x" * 100, key="info.txt")
        info = await self.storage.info("info.txt")
        assert info.key == "info.txt"
        assert info.size == 100
        assert info.etag is not None

    async def test_url(self):
        assert self.storage.url("path/to/file.jpg") == "/media/path/to/file.jpg"

    async def test_save_no_overwrite(self):
        await self.storage.save(b"first", key="nooverwrite.txt")
        with pytest.raises(StorageFileExistsError):
            await self.storage.save(b"second", key="nooverwrite.txt", overwrite=False)

    async def test_presigned_download_url(self):
        result = await self.storage.presigned_download_url("file.txt", expires=3600)
        assert isinstance(result, PresignedUrl)
        assert "file.txt" in result.url
        assert result.method == "GET"

    async def test_presigned_upload_url(self):
        result = await self.storage.presigned_upload_url("upload.jpg", expires=3600)
        assert isinstance(result, PresignedUrl)
        assert result.method == "POST"
        assert result.fields["key"] == "upload.jpg"

    async def test_verify_signature_valid(self):
        result = await self.storage.presigned_download_url("test.txt", expires=3600)
        import urllib.parse

        parsed = urllib.parse.urlparse(result.url)
        params = urllib.parse.parse_qs(parsed.query)
        token = params["token"][0]
        sig = params["signature"][0]
        payload = self.storage.verify_signature(token, sig)
        assert payload is not None
        assert payload["key"] == "test.txt"

    async def test_verify_signature_invalid(self):
        payload = self.storage.verify_signature("bad-token", "bad-sig")
        assert payload is None


# ==============================================================================
# S3Storage (mocked)
# ==============================================================================


class TestS3Storage:
    def test_url_default(self):
        from django_matt.files.s3 import S3Storage

        storage = S3Storage(bucket="my-bucket", region="us-east-1")
        url = storage.url("images/photo.jpg")
        assert url == "https://my-bucket.s3.us-east-1.amazonaws.com/images/photo.jpg"

    def test_url_custom_public_url(self):
        from django_matt.files.s3 import S3Storage

        storage = S3Storage(bucket="b", public_url="https://cdn.example.com")
        assert storage.url("file.txt") == "https://cdn.example.com/file.txt"

    def test_url_custom_endpoint(self):
        from django_matt.files.s3 import S3Storage

        storage = S3Storage(bucket="b", endpoint="http://minio:9000")
        assert storage.url("file.txt") == "http://minio:9000/b/file.txt"

    def test_r2_storage_endpoint(self):
        from django_matt.files.s3 import R2Storage

        storage = R2Storage(
            bucket="b",
            account_id="abc123",
            access_key="ak",
            secret_key="sk",
        )
        assert storage.region == "auto"
        assert "abc123.r2.cloudflarestorage.com" in storage.endpoint

    def test_minio_storage_defaults(self):
        from django_matt.files.s3 import MinIOStorage

        storage = MinIOStorage(bucket="test")
        assert storage.access_key == "minioadmin"
        assert storage.secret_key == "minioadmin"
        assert storage.addressing_style == "path"

    def test_do_spaces_storage(self):
        from django_matt.files.s3 import DOSpacesStorage

        storage = DOSpacesStorage(
            bucket="space",
            region="nyc3",
            access_key="ak",
            secret_key="sk",
        )
        assert "nyc3.digitaloceanspaces.com" in storage.endpoint
        assert storage.public_url == "https://space.nyc3.digitaloceanspaces.com"


# ==============================================================================
# MultipartParser
# ==============================================================================


class TestMultipartParser:
    def test_parse_simple(self):
        body = (
            b"------boundary\r\n"
            b'Content-Disposition: form-data; name="field1"\r\n'
            b"\r\n"
            b"value1\r\n"
            b"------boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"file content\r\n"
            b"------boundary--"
        )

        parser = MultipartParser(
            content_type="multipart/form-data; boundary=----boundary",
            body=body,
        )
        form_data, files = parser.parse()
        assert form_data["field1"] == "value1"
        assert len(files) == 1
        assert files[0].filename == "test.txt"
        assert files[0].read() == b"file content"


# ==============================================================================
# FileConfig
# ==============================================================================


class TestFileConfig:
    def test_defaults(self):
        config = FileConfig()
        assert config.default_storage == "local"
        assert config.max_file_size == 10 * 1024 * 1024
        assert "jpg" in config.allowed_extensions
        assert config.chunk_size == 8192
        assert config.generate_unique_names is True

    def test_from_django_settings(self):
        with patch("django.conf.settings") as mock_settings:
            mock_settings.DJANGO_MATT_FILES = {
                "DEFAULT_STORAGE": "s3",
                "S3_BUCKET": "my-bucket",
                "MAX_FILE_SIZE": 50 * 1024 * 1024,
            }
            config = FileConfig.from_django_settings()
            assert config.default_storage == "s3"
            assert config.s3_bucket == "my-bucket"
            assert config.max_file_size == 50 * 1024 * 1024


# ==============================================================================
# S3Storage Mock Tests (07-03)
# ==============================================================================


@pytest.mark.asyncio
class TestS3StorageWithMock:
    """Tests for S3Storage with mocked boto3 client.

    Verifies:
    - save() calls put_object
    - presigned_download_url() returns signed URL
    - R2Storage sets correct endpoint
    - MinIOStorage sets correct endpoint
    - File upload validator rejects oversized files
    """

    @pytest.fixture(autouse=True)
    def setup_storage(self):
        from django_matt.files.s3 import S3Storage

        self.storage = S3Storage(
            bucket="test-bucket",
            region="us-east-1",
            access_key="AKTEST",
            secret_key="SECRET",
        )
        # Pre-create a mock client
        self.mock_client = MagicMock()
        self.storage._client = self.mock_client

    async def test_save_calls_put_object(self):
        """Test: S3Storage.save() calls put_object with correct params."""
        content = b"hello world"
        self.mock_client.put_object.return_value = {}

        key = await self.storage.save(
            content,
            key="test.txt",
            content_type="text/plain",
        )

        assert key == "test.txt"
        self.mock_client.put_object.assert_called_once()
        call_kwargs = self.mock_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "test.txt"
        assert call_kwargs["Body"] == content
        assert call_kwargs["ContentType"] == "text/plain"

    async def test_presigned_download_url_returns_url(self):
        """Test: presigned_download_url() returns a PresignedUrl with signed URL."""
        self.mock_client.generate_presigned_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/file.txt?X-Amz-Signature=abc123"
        )

        result = await self.storage.presigned_download_url("file.txt", expires=3600)

        assert isinstance(result, PresignedUrl)
        assert "X-Amz-Signature=abc123" in result.url
        assert result.method == "GET"
        assert result.expires_at is not None

        self.mock_client.generate_presigned_url.assert_called_once()
        call_args = self.mock_client.generate_presigned_url.call_args
        assert call_args[0][0] == "get_object"
        assert call_args[1]["Params"]["Bucket"] == "test-bucket"
        assert call_args[1]["Params"]["Key"] == "file.txt"
        assert call_args[1]["ExpiresIn"] == 3600

    async def test_save_with_folder_prepends_path(self):
        """Test: save() with folder prepends folder to key."""
        self.mock_client.put_object.return_value = {}

        key = await self.storage.save(
            b"data",
            key="file.txt",
            folder="uploads",
        )

        assert key == "uploads/file.txt"

    def test_r2_storage_sets_correct_endpoint(self):
        """Test: R2Storage configures R2-specific endpoint."""
        from django_matt.files.s3 import R2Storage

        storage = R2Storage(
            bucket="r2-bucket",
            account_id="acc123",
            access_key="ak",
            secret_key="sk",
        )
        assert storage.endpoint == "https://acc123.r2.cloudflarestorage.com"
        assert storage.region == "auto"

    def test_minio_storage_sets_correct_endpoint(self):
        """Test: MinIOStorage configures MinIO-specific settings."""
        from django_matt.files.s3 import MinIOStorage

        storage = MinIOStorage(
            bucket="minio-bucket",
            endpoint="http://localhost:9000",
        )
        assert storage.endpoint == "http://localhost:9000"
        assert storage.addressing_style == "path"
        assert storage.use_ssl is False

    def test_file_upload_validator_rejects_oversized(self):
        """Test: FileValidator rejects files exceeding max_size."""
        validator = FileValidator(max_size=100)
        oversized = UploadedFile.from_bytes(b"x" * 200, filename="big.txt")

        with pytest.raises(FileTooLargeError):
            validator.validate(oversized)
