"""
Image processing pipeline.

Provides a fluent API for resizing, converting, and optimizing images.
Uses Pillow when available, raises helpful ImportError otherwise.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from functools import wraps
from typing import Any, BinaryIO, Callable

logger = logging.getLogger("django_matt.files.processing")

_PIL_AVAILABLE = False
try:
    from PIL import Image, ImageOps

    _PIL_AVAILABLE = True
except ImportError:
    pass


def _require_pillow() -> None:
    if not _PIL_AVAILABLE:
        raise ImportError("Pillow is required for image processing. Install with: uv add Pillow")


@dataclass
class ProcessedImage:
    """Result of an image processing pipeline."""

    file: BinaryIO
    width: int
    height: int
    format: str
    size_bytes: int
    thumbnail: ProcessedImage | None = None


class ImageProcessor:
    """
    Fluent image processing pipeline.

    Usage::

        result = (
            ImageProcessor()
            .resize(800, 600)
            .convert("webp")
            .quality(85)
            .strip_metadata()
            .process(file)
        )
        # result.file is a BytesIO with the processed image
    """

    def __init__(self) -> None:
        _require_pillow()
        self._steps: list[tuple[str, dict[str, Any]]] = []
        self._output_format: str | None = None
        self._output_quality: int = 85
        self._thumbnail_size: tuple[int, int] | None = None
        self._strip_meta: bool = False

    def resize(
        self,
        width: int,
        height: int,
        mode: str = "cover",
    ) -> ImageProcessor:
        """
        Resize the image.

        Args:
            width: Target width in pixels.
            height: Target height in pixels.
            mode: Resize strategy.
                - "cover": Crop to fill exact dimensions (default).
                - "contain": Fit within dimensions, preserving aspect ratio.
                - "fill": Stretch to exact dimensions (may distort).
        """
        self._steps.append(("resize", {"width": width, "height": height, "mode": mode}))
        return self

    def convert(self, fmt: str = "webp") -> ImageProcessor:
        """
        Convert the image to the specified format.

        Supported: "webp", "avif", "png", "jpeg".
        """
        self._output_format = fmt.lower()
        return self

    def quality(self, q: int) -> ImageProcessor:
        """Set output quality (1-100). Applies to JPEG, WebP, AVIF."""
        self._output_quality = max(1, min(100, q))
        return self

    def thumbnail(self, width: int, height: int) -> ImageProcessor:
        """Generate a thumbnail alongside the main image."""
        self._thumbnail_size = (width, height)
        return self

    def strip_metadata(self) -> ImageProcessor:
        """Remove EXIF and other metadata from the image."""
        self._strip_meta = True
        return self

    def process(self, file: BinaryIO | bytes) -> ProcessedImage:
        """
        Execute the processing pipeline on the given file.

        Args:
            file: Image file as bytes or file-like object.

        Returns:
            ProcessedImage with the processed file and metadata.
        """
        _require_pillow()

        if isinstance(file, bytes):
            file = io.BytesIO(file)

        img = Image.open(file)

        # Convert palette/RGBA as needed for JPEG output
        target_fmt = self._output_format or (img.format or "png").lower()

        for step_name, params in self._steps:
            if step_name == "resize":
                img = self._apply_resize(img, **params)

        if self._strip_meta:
            img = self._apply_strip_metadata(img)

        # Generate thumbnail before saving main image
        thumb_result: ProcessedImage | None = None
        if self._thumbnail_size:
            thumb_result = self._make_thumbnail(img, self._thumbnail_size, target_fmt)

        # Save main image
        output = self._save_image(img, target_fmt)
        output.seek(0, 2)
        size_bytes = output.tell()
        output.seek(0)

        return ProcessedImage(
            file=output,
            width=img.width,
            height=img.height,
            format=target_fmt,
            size_bytes=size_bytes,
            thumbnail=thumb_result,
        )

    def _apply_resize(
        self,
        img: Any,
        width: int,
        height: int,
        mode: str,
    ) -> Any:
        if mode == "cover":
            img = ImageOps.fit(img, (width, height), method=Image.LANCZOS)
        elif mode == "contain":
            img.thumbnail((width, height), Image.LANCZOS)
        elif mode == "fill":
            img = img.resize((width, height), Image.LANCZOS)
        else:
            raise ValueError(f"Unknown resize mode: {mode}")
        return img

    def _apply_strip_metadata(self, img: Any) -> Any:
        data = list(img.getdata())
        clean = Image.new(img.mode, img.size)
        clean.putdata(data)
        return clean

    def _make_thumbnail(
        self,
        img: Any,
        size: tuple[int, int],
        fmt: str,
    ) -> ProcessedImage:
        thumb = img.copy()
        thumb.thumbnail(size, Image.LANCZOS)
        output = self._save_image(thumb, fmt)
        output.seek(0, 2)
        size_bytes = output.tell()
        output.seek(0)
        return ProcessedImage(
            file=output,
            width=thumb.width,
            height=thumb.height,
            format=fmt,
            size_bytes=size_bytes,
            thumbnail=None,
        )

    def _save_image(self, img: Any, fmt: str) -> io.BytesIO:
        output = io.BytesIO()
        pil_format = _FORMAT_MAP.get(fmt, fmt.upper())

        save_kwargs: dict[str, Any] = {"format": pil_format}

        if pil_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = self._output_quality
            save_kwargs["optimize"] = True

        if pil_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        if pil_format == "PNG":
            save_kwargs["optimize"] = True

        img.save(output, **save_kwargs)
        return output


# Map common format names to Pillow format strings
_FORMAT_MAP: dict[str, str] = {
    "jpeg": "JPEG",
    "jpg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "avif": "AVIF",
    "gif": "GIF",
    "bmp": "BMP",
    "tiff": "TIFF",
}


def process_image(
    resize: tuple[int, int] | None = None,
    format: str | None = None,
    quality: int = 85,
    thumbnail: tuple[int, int] | None = None,
    strip_metadata: bool = False,
    mode: str = "cover",
) -> Callable:
    """
    Decorator for upload handlers that auto-processes uploaded images.

    The decorated function must accept a file-like object as its first
    positional argument (after self if it's a method). The decorator replaces
    the raw file with a ProcessedImage.

    Usage::

        @process_image(resize=(800, 600), format="webp", quality=85, thumbnail=(200, 200))
        async def handle_upload(file):
            # file is now a ProcessedImage
            return file

    Args:
        resize: (width, height) to resize to.
        format: Output format ("webp", "jpeg", "png", etc.).
        quality: Output quality (1-100).
        thumbnail: (width, height) for thumbnail generation.
        strip_metadata: Whether to remove EXIF data.
        mode: Resize mode ("cover", "contain", "fill").
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            processor = ImageProcessor()
            if resize:
                processor = processor.resize(resize[0], resize[1], mode=mode)
            if format:
                processor = processor.convert(format)
            processor = processor.quality(quality)
            if strip_metadata:
                processor = processor.strip_metadata()
            if thumbnail:
                processor = processor.thumbnail(thumbnail[0], thumbnail[1])

            # Find the file argument (first positional or "file" kwarg)
            file_arg = kwargs.get("file")
            if file_arg is None and args:
                # Try first arg; if it looks like self/cls, try second
                candidate = args[0]
                if hasattr(candidate, "read") or isinstance(candidate, bytes):
                    file_arg = candidate
                    args = args[1:]
                elif len(args) > 1:
                    file_arg = args[1]
                    args = (args[0], *args[2:])

            if file_arg is not None:
                processed = processor.process(file_arg)
                kwargs["file"] = processed

            return await fn(*args, **kwargs)

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            processor = ImageProcessor()
            if resize:
                processor = processor.resize(resize[0], resize[1], mode=mode)
            if format:
                processor = processor.convert(format)
            processor = processor.quality(quality)
            if strip_metadata:
                processor = processor.strip_metadata()
            if thumbnail:
                processor = processor.thumbnail(thumbnail[0], thumbnail[1])

            file_arg = kwargs.get("file")
            if file_arg is None and args:
                candidate = args[0]
                if hasattr(candidate, "read") or isinstance(candidate, bytes):
                    file_arg = candidate
                    args = args[1:]
                elif len(args) > 1:
                    file_arg = args[1]
                    args = (args[0], *args[2:])

            if file_arg is not None:
                processed = processor.process(file_arg)
                kwargs["file"] = processed

            return fn(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator
