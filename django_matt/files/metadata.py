"""
Automatic file metadata extraction.

Extracts metadata from uploaded files: MIME type, checksum, dimensions,
duration, codec info, page counts. Gracefully degrades when optional
dependencies (Pillow, ffprobe, pypdf) are missing.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import mimetypes
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, BinaryIO

logger = logging.getLogger("django_matt.files.metadata")


@dataclass
class FileMetadata:
    """Extracted metadata for any file type."""

    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    checksum_sha256: str = ""

    # Image fields (populated when file is an image and Pillow is available)
    width: int | None = None
    height: int | None = None
    image_format: str | None = None
    has_alpha: bool | None = None
    exif: dict[str, Any] = field(default_factory=dict)

    # Video fields (populated when ffprobe is available)
    video_duration: float | None = None
    video_width: int | None = None
    video_height: int | None = None
    video_codec: str | None = None
    video_fps: float | None = None

    # Audio fields (populated when ffprobe is available)
    audio_duration: float | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None
    audio_codec: str | None = None

    # Document fields
    page_count: int | None = None


def _read_bytes(file: BinaryIO | bytes) -> bytes:
    if isinstance(file, bytes):
        return file
    pos = file.tell()
    data = file.read()
    file.seek(pos)
    return data


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _guess_mime(data: bytes, filename: str | None = None) -> str:
    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed

    # Sniff common magic bytes
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:4] in (b"ID3\x03", b"ID3\x04", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"

    return "application/octet-stream"


def _extract_image_metadata(data: bytes, meta: FileMetadata) -> None:
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
    except ImportError:
        logger.debug("Pillow not installed, skipping image metadata extraction")
        return

    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        return

    meta.width = img.width
    meta.height = img.height
    meta.image_format = (img.format or "").lower()
    meta.has_alpha = img.mode in ("RGBA", "LA", "PA")

    # Extract EXIF
    try:
        exif_data = img.getexif()
        if exif_data:
            meta.exif = {
                TAGS.get(tag, str(tag)): str(value)
                for tag, value in exif_data.items()
            }
    except Exception:
        pass


def _extract_av_metadata(data: bytes, meta: FileMetadata) -> None:
    """Extract audio/video metadata using ffprobe."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        logger.debug("ffprobe not found, skipping audio/video metadata extraction")
        return

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                "pipe:0",
            ],
            input=data,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            return

        info = json.loads(result.stdout)
    except Exception:
        logger.debug("ffprobe failed", exc_info=True)
        return

    streams = info.get("streams", [])
    fmt = info.get("format", {})

    for stream in streams:
        codec_type = stream.get("codec_type")

        if codec_type == "video":
            meta.video_width = int(stream.get("width", 0)) or None
            meta.video_height = int(stream.get("height", 0)) or None
            meta.video_codec = stream.get("codec_name")

            # Parse fps from r_frame_rate (e.g., "30/1")
            r_fps = stream.get("r_frame_rate", "")
            if "/" in r_fps:
                num, den = r_fps.split("/")
                try:
                    meta.video_fps = round(int(num) / int(den), 2)
                except (ValueError, ZeroDivisionError):
                    pass

            duration = stream.get("duration") or fmt.get("duration")
            if duration:
                try:
                    meta.video_duration = round(float(duration), 3)
                except ValueError:
                    pass

        elif codec_type == "audio":
            meta.audio_codec = stream.get("codec_name")

            sample_rate = stream.get("sample_rate")
            if sample_rate:
                try:
                    meta.audio_sample_rate = int(sample_rate)
                except ValueError:
                    pass

            channels = stream.get("channels")
            if channels:
                try:
                    meta.audio_channels = int(channels)
                except ValueError:
                    pass

            duration = stream.get("duration") or fmt.get("duration")
            if duration:
                try:
                    meta.audio_duration = round(float(duration), 3)
                except ValueError:
                    pass


def _extract_pdf_metadata(data: bytes, meta: FileMetadata) -> None:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.debug("pypdf not installed, skipping PDF metadata extraction")
        return

    try:
        reader = PdfReader(io.BytesIO(data))
        meta.page_count = len(reader.pages)
    except Exception:
        logger.debug("Failed to extract PDF metadata", exc_info=True)


def extract_metadata(
    file: BinaryIO | bytes,
    filename: str | None = None,
) -> FileMetadata:
    """
    Extract metadata from a file.

    Detects file type and extracts all available metadata. Gracefully
    degrades when optional dependencies are missing.

    Args:
        file: File content as bytes or file-like object.
        filename: Optional filename for MIME type guessing.

    Returns:
        FileMetadata with all extractable fields populated.
    """
    data = _read_bytes(file)

    mime = _guess_mime(data, filename)
    checksum = _compute_checksum(data)

    meta = FileMetadata(
        mime_type=mime,
        size_bytes=len(data),
        checksum_sha256=checksum,
    )

    # Route to type-specific extractors
    if mime.startswith("image/"):
        _extract_image_metadata(data, meta)

    elif mime.startswith("video/") or mime.startswith("audio/"):
        _extract_av_metadata(data, meta)

    elif mime == "application/pdf":
        _extract_pdf_metadata(data, meta)

    return meta
