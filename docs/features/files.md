# File Handling

Upload and manage files with multiple storage backends.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "FILES": {
        "STORAGE_BACKEND": "s3",  # or "local", "r2", "minio", "do-spaces"
        "MAX_UPLOAD_SIZE": 10 * 1024 * 1024,  # 10 MB
        "ALLOWED_TYPES": ["image/jpeg", "image/png", "application/pdf"],
        "S3": {
            "BUCKET_NAME": "my-bucket",
            "REGION": "us-east-1",
            "ACCESS_KEY_ID": os.environ["AWS_ACCESS_KEY_ID"],
            "SECRET_ACCESS_KEY": os.environ["AWS_SECRET_ACCESS_KEY"],
        },
    },
}
```

## File Upload

### Basic Upload

```python
from django_matt.files import UploadedFile

@api.post("/upload")
async def upload_file(request, file: UploadedFile):
    # Save to storage
    url = await file.save("uploads/")
    return {"url": url}
```

### With Validation

```python
from django_matt.files import FileValidator

validator = FileValidator(
    max_size=5 * 1024 * 1024,  # 5 MB
    allowed_types=["image/jpeg", "image/png"],
    allowed_extensions=[".jpg", ".jpeg", ".png"],
)

@api.post("/upload/image")
async def upload_image(request, file: UploadedFile):
    validator.validate(file)
    url = await file.save("images/")
    return {"url": url}
```

### Pre-built Validators

```python
from django_matt.files import FileValidator

# Image validator
images_validator = FileValidator.images(max_size=5 * 1024 * 1024)

# Document validator
docs_validator = FileValidator.documents(max_size=10 * 1024 * 1024)

# Video validator
video_validator = FileValidator.videos(max_size=100 * 1024 * 1024)

# Audio validator
audio_validator = FileValidator.audio(max_size=20 * 1024 * 1024)
```

## Storage Backends

### Local Storage

```python
from django_matt.files import LocalStorage

storage = LocalStorage(base_path="/var/www/uploads")

# Save file
path = await storage.save(file, "uploads/image.jpg")

# Get URL
url = storage.url(path)

# Delete file
await storage.delete(path)
```

### S3 Storage

```python
from django_matt.files import S3Storage

storage = S3Storage(
    bucket_name="my-bucket",
    region="us-east-1",
    access_key_id="...",
    secret_access_key="...",
)

# Save file
url = await storage.save(file, "uploads/image.jpg")

# Generate presigned URL
presigned_url = await storage.presigned_url("uploads/image.jpg", expires_in=3600)
```

### Cloudflare R2

```python
from django_matt.files import R2Storage

storage = R2Storage(
    account_id="...",
    bucket_name="my-bucket",
    access_key_id="...",
    secret_access_key="...",
)
```

### MinIO

```python
from django_matt.files import MinIOStorage

storage = MinIOStorage(
    endpoint="localhost:9000",
    bucket_name="my-bucket",
    access_key="...",
    secret_key="...",
    secure=False,
)
```

### DigitalOcean Spaces

```python
from django_matt.files import DOSpacesStorage

storage = DOSpacesStorage(
    region="nyc3",
    space_name="my-space",
    access_key_id="...",
    secret_access_key="...",
)
```

## Presigned URLs

### Upload URLs

```python
@api.post("/upload/presigned")
async def get_upload_url(request, data: UploadRequest):
    storage = get_storage()

    # Generate presigned upload URL
    url = await storage.presigned_upload_url(
        key=f"uploads/{data.filename}",
        content_type=data.content_type,
        expires_in=3600,
    )

    return {"upload_url": url, "key": f"uploads/{data.filename}"}
```

### Download URLs

```python
@api.get("/files/{file_id}/download")
async def get_download_url(request, file_id: int):
    file = await File.objects.aget(id=file_id)
    storage = get_storage()

    url = await storage.presigned_url(
        file.path,
        expires_in=3600,
    )

    return {"download_url": url}
```

## Streaming Uploads

```python
from django_matt.files import MultipartParser

@api.post("/upload/large")
async def upload_large_file(request):
    parser = MultipartParser(request)

    async for chunk in parser.stream():
        # Process chunks
        await storage.write_chunk(chunk)

    return {"message": "Upload complete"}
```

## Using Factory

```python
from django_matt.files import get_storage

# Get storage from settings
storage = get_storage()

# Or specify backend
storage = get_storage("s3")
storage = get_storage("local")
```
