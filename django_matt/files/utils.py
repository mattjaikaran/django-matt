"""
File utility functions.

Provides helper functions for file handling.
"""

import mimetypes
import os
import re
import uuid
from datetime import UTC, datetime


def get_file_extension(filename: str) -> str:
    """
    Get the file extension from a filename.

    Args:
        filename: The filename to extract extension from

    Returns:
        Lowercase extension without dot, or empty string
    """
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


def get_content_type(filename: str, default: str = "application/octet-stream") -> str:
    """
    Get the MIME content type for a filename.

    Args:
        filename: The filename to get content type for
        default: Default content type if not detected

    Returns:
        MIME type string
    """
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or default


def generate_unique_filename(
    filename: str = None,
    extension: str = None,
    prefix: str = None,
    include_timestamp: bool = True,
) -> str:
    """
    Generate a unique filename.

    Args:
        filename: Original filename to base on (optional)
        extension: File extension without dot (optional)
        prefix: Prefix to add (optional)
        include_timestamp: Whether to include timestamp

    Returns:
        Unique filename string
    """
    # Get extension from original filename or use provided
    if extension is None and filename:
        extension = get_file_extension(filename)

    # Generate unique part
    unique_id = uuid.uuid4().hex[:12]

    # Build filename parts
    parts = []

    if prefix:
        parts.append(prefix)

    if include_timestamp:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        parts.append(timestamp)

    parts.append(unique_id)

    # Join and add extension
    name = "_".join(parts)

    if extension:
        name = f"{name}.{extension}"

    return name


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to be safe for filesystem storage.

    Removes or replaces dangerous characters and limits length.

    Args:
        filename: The filename to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized filename
    """
    # Get name and extension
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
        ext = ext.lower()
    else:
        name, ext = filename, ""

    # Remove directory separators
    name = name.replace("/", "_").replace("\\", "_")

    # Remove or replace dangerous characters
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "", name)

    # Replace multiple spaces/underscores with single underscore
    name = re.sub(r"[\s_]+", "_", name)

    # Remove leading/trailing spaces and dots
    name = name.strip(" ._")

    # Limit length (accounting for extension)
    if ext:
        max_name_length = max_length - len(ext) - 1
        name = name[:max_name_length]
        return f"{name}.{ext}"

    return name[:max_length]


def human_readable_size(size: int) -> str:
    """
    Convert bytes to human readable format.

    Args:
        size: Size in bytes

    Returns:
        Human readable string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def parse_size(size_str: str) -> int:
    """
    Parse a human readable size string to bytes.

    Args:
        size_str: Size string (e.g., "10MB", "1.5 GB")

    Returns:
        Size in bytes
    """
    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "PB": 1024**5,
    }

    size_str = size_str.strip().upper()

    # Try to match number and unit
    match = re.match(r"^([\d.]+)\s*([A-Z]{1,2})?$", size_str)
    if not match:
        raise ValueError(f"Invalid size string: {size_str}")

    number = float(match.group(1))
    unit = match.group(2) or "B"

    if unit not in units:
        raise ValueError(f"Unknown unit: {unit}")

    return int(number * units[unit])


def get_safe_path(base: str, *parts: str) -> str:
    """
    Safely join path parts, preventing directory traversal.

    Args:
        base: Base directory
        *parts: Path parts to join

    Returns:
        Safe absolute path

    Raises:
        ValueError: If path would escape base directory
    """
    # Normalize base
    base = os.path.abspath(base)

    # Join and normalize
    full_path = os.path.abspath(os.path.join(base, *parts))

    # Check that result is under base
    if not full_path.startswith(base + os.sep) and full_path != base:
        raise ValueError(f"Path {full_path} is outside base directory {base}")

    return full_path


def split_filename(filename: str) -> tuple[str, str]:
    """
    Split a filename into name and extension.

    Args:
        filename: The filename to split

    Returns:
        Tuple of (name, extension) where extension doesn't include dot
    """
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
        return name, ext.lower()
    return filename, ""


def is_image(content_type: str) -> bool:
    """Check if content type is an image."""
    return content_type.startswith("image/")


def is_video(content_type: str) -> bool:
    """Check if content type is a video."""
    return content_type.startswith("video/")


def is_audio(content_type: str) -> bool:
    """Check if content type is audio."""
    return content_type.startswith("audio/")


def is_document(content_type: str) -> bool:
    """Check if content type is a document (PDF, Office, etc)."""
    document_types = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "text/html",
        "text/markdown",
    }
    return content_type in document_types
