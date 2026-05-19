# File Uploads

Direct uploads, S3/R2/MinIO backends, validation, chunked/resumable uploads, and presigned URLs.

---

## Settings

```python
DJANGO_MATT_FILES = {
    "DEFAULT_STORAGE": "s3",       # "local" | "s3" | "r2" | "minio" | "spaces"
    "S3_BUCKET": env("S3_BUCKET"),
    "S3_REGION": "us-east-1",
    "S3_ACCESS_KEY": env("AWS_ACCESS_KEY_ID"),
    "S3_SECRET_KEY": env("AWS_SECRET_ACCESS_KEY"),
    # R2 / MinIO — set endpoint instead
    # "S3_ENDPOINT": "https://<account>.r2.cloudflarestorage.com",
    # "S3_PUBLIC_URL": "https://assets.example.com",
    "MAX_FILE_SIZE": 10 * 1024 * 1024,   # 10 MB
    "ALLOWED_EXTENSIONS": ["jpg", "jpeg", "png", "gif", "pdf", "webp"],
}
```

### Storage backends

| Value | Backend |
|-------|---------|
| `"local"` | Local filesystem |
| `"s3"` | AWS S3 |
| `"r2"` | Cloudflare R2 (set `S3_ENDPOINT`) |
| `"minio"` | Self-hosted MinIO (set `S3_ENDPOINT`) |
| `"spaces"` | DigitalOcean Spaces |

---

## Basic Upload Endpoint

```python
from django_matt.core.controller import APIController
from django_matt.core.router import post
from django_matt.auth.decorators import jwt_required
from django_matt.files import get_storage, UploadedFile, FileValidator
from django_matt.files.exceptions import FileTooLargeError, InvalidFileTypeError

class UploadController(APIController):
    prefix = "/uploads"

    @post("/")
    @jwt_required
    async def upload(self, request):
        file = UploadedFile.from_request(request, field_name="file")
        if file is None:
            return self.error("No file provided", status=400)

        validator = FileValidator(
            max_size=5 * 1024 * 1024,
            allowed_extensions=["jpg", "jpeg", "png", "pdf"],
        )
        try:
            validator.validate(file)
        except (FileTooLargeError, InvalidFileTypeError) as exc:
            return self.error(str(exc), status=422)

        storage = get_storage()
        key = await storage.save(
            file,
            folder=f"users/{request.user.id}",
        )
        url = await storage.presigned_download_url(key, expires=3600)
        return {"key": key, "url": url}
```

---

## Presigned Uploads (client-side direct upload)

Generate a short-lived URL so the browser uploads directly to S3/R2, bypassing your server.

```python
from django_matt.files import get_storage
from django_matt.files.presigned import generate_presigned_upload

class UploadController(APIController):
    prefix = "/uploads"

    @post("/presigned")
    @jwt_required
    async def presigned(self, request):
        body = await request.json()
        filename = body["filename"]
        content_type = body.get("content_type", "application/octet-stream")

        storage = get_storage()
        key = f"uploads/{request.user.id}/{filename}"
        presigned = await generate_presigned_upload(
            storage,
            key=key,
            content_type=content_type,
            expires=300,           # 5 minutes
            max_size=20_000_000,   # 20 MB
        )
        return {
            "url": presigned.url,
            "fields": presigned.fields,    # POST form fields (S3-style)
            "headers": presigned.headers,  # PUT headers (R2-style)
            "expires_at": presigned.expires_at.isoformat(),
            "key": key,
        }
```

### Frontend (fetch)

```typescript
// 1. Get presigned data from your API
const { url, fields, key } = await api.post("/uploads/presigned", {
  filename: file.name,
  content_type: file.type,
});

// 2. Upload directly to S3/R2
const form = new FormData();
Object.entries(fields).forEach(([k, v]) => form.append(k, v as string));
form.append("file", file);
await fetch(url, { method: "POST", body: form });

// 3. Tell your backend about the uploaded key
await api.post("/documents", { storage_key: key });
```

---

## Presigned Download URLs

Generate time-limited download links without exposing private S3 URLs:

```python
storage = get_storage()

# Inline (preview in browser)
url = await storage.presigned_download_url(key, expires=3600)

# Force download with a specific filename
url = await storage.presigned_download_url(
    key,
    expires=3600,
    filename="invoice-2024.pdf",
)
```

---

## Chunked / Resumable Uploads (tus protocol)

For large files (video, datasets) use the built-in tus v1.0.0 handler:

```python
from django_matt.files.chunked import TusUploadHandler, TusUploadView
from django_matt.files import get_storage

# Wire up the tus view
storage = get_storage()
handler = TusUploadHandler(storage=storage)

urlpatterns = [
    path("uploads/tus/", TusUploadView.as_view(handler=handler)),
]
```

The tus protocol:

```
# 1. Create upload session
POST /uploads/tus/
Upload-Length: 104857600
Upload-Metadata: filename dmlkZW8ubXA0,content-type dmlkZW8vbXA0

→ 201 Created
Location: /uploads/tus/<upload-id>

# 2. Upload chunks
PATCH /uploads/tus/<upload-id>
Content-Type: application/offset+octet-stream
Upload-Offset: 0
Content-Length: 5242880

<bytes>

→ 204 No Content
Upload-Offset: 5242880

# 3. Resume (check offset after interruption)
HEAD /uploads/tus/<upload-id>
→ 200 OK
Upload-Offset: 5242880
Upload-Length: 104857600
```

### S3 native multipart (large files)

```python
from django_matt.files.chunked import S3MultipartHandler
from django_matt.files import get_storage

storage = get_storage()
handler = S3MultipartHandler(storage=storage)

# Create
upload_id = await handler.create_multipart(
    key="videos/my-video.mp4",
    content_type="video/mp4",
)

# Upload parts (minimum 5 MB each, except last)
etag1 = await handler.upload_part(upload_id, part_number=1, body=chunk1)
etag2 = await handler.upload_part(upload_id, part_number=2, body=chunk2)

# Complete
await handler.complete_multipart(
    upload_id,
    parts=[
        {"PartNumber": 1, "ETag": etag1},
        {"PartNumber": 2, "ETag": etag2},
    ],
)

# Abort on error
await handler.abort_multipart(upload_id)
```

---

## File Validation

```python
from django_matt.files import FileValidator, UploadedFile
from django_matt.files.exceptions import FileTooLargeError, InvalidFileTypeError, InvalidExtensionError

validator = FileValidator(
    max_size=10 * 1024 * 1024,                           # 10 MB
    allowed_types=["image/jpeg", "image/png", "application/pdf"],
    allowed_extensions=["jpg", "jpeg", "png", "pdf"],
)

try:
    validator.validate(uploaded_file)
except FileTooLargeError:
    ...  # file exceeds max_size
except InvalidFileTypeError:
    ...  # MIME type not allowed
except InvalidExtensionError:
    ...  # extension not allowed
```

---

## Storage API Reference

```python
from django_matt.files import get_storage

storage = get_storage()   # uses DEFAULT_STORAGE from settings

# Save
key = await storage.save(file, key=None, folder=None, content_type=None, metadata=None)

# Read
data: bytes = await storage.get(key)

# Stream (large files)
async for chunk in storage.get_stream(key, chunk_size=8192):
    ...

# Delete
await storage.delete(key)

# Check existence
exists: bool = await storage.exists(key)

# List
files, next_cursor = await storage.list(prefix="uploads/", limit=100, cursor=None)

# Presigned upload URL
presigned = await storage.presigned_upload_url(
    key, expires=3600, content_type="image/png"
)

# Presigned download URL
url: str = await storage.presigned_download_url(key, expires=3600, filename=None)
```

---

## Switching Backends

```python
from django_matt.files.backends import S3Storage, R2Storage, MinIOStorage, LocalStorage

# Explicit backend
r2 = R2Storage(
    bucket=env("R2_BUCKET"),
    endpoint=env("R2_ENDPOINT"),    # https://<account>.r2.cloudflarestorage.com
    access_key=env("R2_ACCESS_KEY"),
    secret_key=env("R2_SECRET_KEY"),
    public_url=env("R2_PUBLIC_URL"),
)

minio = MinIOStorage(
    bucket="dev-uploads",
    endpoint="http://localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
)
```
