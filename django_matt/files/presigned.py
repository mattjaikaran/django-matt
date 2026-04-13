"""
Presigned URL generation for direct client-to-storage uploads/downloads.

Works with S3, R2, MinIO, Backblaze B2, and any S3-compatible backend.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger("django_matt.files.presigned")


@dataclass
class PresignedUpload:
    """
    Result of generating a presigned upload URL.

    Attributes:
        url: The presigned URL to upload to.
        fields: Dict of form fields for multipart/form-data POST uploads (S3 style).
        headers: Dict of headers for PUT uploads.
        expires_at: When the presigned URL expires.
    """

    url: str
    fields: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))


async def generate_presigned_upload(
    storage: Any,
    key: str,
    content_type: str = "application/octet-stream",
    expires: int = 3600,
    conditions: list[Any] | None = None,
    metadata: dict[str, str] | None = None,
    max_size: int | None = None,
    method: str = "POST",
) -> PresignedUpload:
    """
    Generate a presigned URL for direct client-to-storage upload.

    Supports two modes:
    - POST (default): multipart/form-data upload with policy and fields
    - PUT: simple PUT request with signed URL and headers

    Args:
        storage: An S3Storage-compatible instance with `.client` and `.bucket`.
        key: The object key (path) where the file will be stored.
        content_type: MIME type of the file being uploaded.
        expires: URL expiration time in seconds (default 3600).
        conditions: Additional S3 policy conditions for POST uploads.
        metadata: Key-value metadata to attach to the uploaded object.
        max_size: Maximum allowed file size in bytes (POST mode only).
        method: "POST" for form upload, "PUT" for direct PUT.

    Returns:
        PresignedUpload with url, fields/headers, and expiry.
    """
    expires_at = datetime.now(UTC) + timedelta(seconds=expires)

    if method == "PUT":
        return await _generate_put_upload(
            storage, key, content_type, expires, expires_at, metadata
        )

    return await _generate_post_upload(
        storage, key, content_type, expires, expires_at, conditions, metadata, max_size
    )


async def _generate_post_upload(
    storage: Any,
    key: str,
    content_type: str,
    expires: int,
    expires_at: datetime,
    conditions: list[Any] | None,
    metadata: dict[str, str] | None,
    max_size: int | None,
) -> PresignedUpload:
    """Generate a presigned POST upload (multipart/form-data with policy)."""
    policy_conditions: list[Any] = list(conditions or [])
    fields: dict[str, str] = {"key": key}

    if content_type:
        policy_conditions.append({"Content-Type": content_type})
        fields["Content-Type"] = content_type

    if max_size:
        policy_conditions.append(["content-length-range", 0, max_size])

    if metadata:
        for k, v in metadata.items():
            meta_key = f"x-amz-meta-{k}"
            policy_conditions.append({meta_key: str(v)})
            fields[meta_key] = str(v)

    response = await asyncio.to_thread(
        lambda: storage.client.generate_presigned_post(
            Bucket=storage.bucket,
            Key=key,
            Fields=fields,
            Conditions=policy_conditions,
            ExpiresIn=expires,
        )
    )

    return PresignedUpload(
        url=response["url"],
        fields=response["fields"],
        headers={},
        expires_at=expires_at,
    )


async def _generate_put_upload(
    storage: Any,
    key: str,
    content_type: str,
    expires: int,
    expires_at: datetime,
    metadata: dict[str, str] | None,
) -> PresignedUpload:
    """Generate a presigned PUT upload URL."""
    params: dict[str, Any] = {
        "Bucket": storage.bucket,
        "Key": key,
        "ContentType": content_type,
    }

    if metadata:
        for k, v in metadata.items():
            params[f"x-amz-meta-{k}"] = str(v)

    url = await asyncio.to_thread(
        lambda: storage.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires,
        )
    )

    headers = {"Content-Type": content_type}

    return PresignedUpload(
        url=url,
        fields={},
        headers=headers,
        expires_at=expires_at,
    )


async def generate_presigned_download(
    storage: Any,
    key: str,
    expires: int = 3600,
    filename: str | None = None,
) -> str:
    """
    Generate a presigned download URL.

    Args:
        storage: An S3Storage-compatible instance with `.client` and `.bucket`.
        key: The object key to download.
        expires: URL expiration time in seconds (default 3600).
        filename: If provided, sets Content-Disposition for browser download.

    Returns:
        The presigned download URL string.
    """
    params: dict[str, Any] = {
        "Bucket": storage.bucket,
        "Key": key,
    }

    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    url: str = await asyncio.to_thread(
        lambda: storage.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires,
        )
    )

    return url
