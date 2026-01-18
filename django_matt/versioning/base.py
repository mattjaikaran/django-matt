"""
Base versioning class for django-matt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest


class VersioningError(Exception):
    """Raised when version detection or validation fails."""

    def __init__(
        self,
        message: str = "Invalid API version",
        version: str | None = None,
        allowed_versions: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.version = version
        self.allowed_versions = allowed_versions


class BaseVersioning(ABC):
    """
    Base class for API versioning schemes.

    Subclasses must implement `determine_version` to extract the
    version from requests using their specific scheme.
    """

    # Default version when none is specified
    default_version: str | None = None

    # List of allowed versions (None = all versions allowed)
    allowed_versions: list[str] | None = None

    def __init__(
        self,
        default_version: str | None = None,
        allowed_versions: list[str] | None = None,
    ) -> None:
        """
        Initialize the versioning scheme.

        Args:
            default_version: Version to use when none specified
            allowed_versions: List of valid version strings
        """
        if default_version is not None:
            self.default_version = default_version
        if allowed_versions is not None:
            self.allowed_versions = allowed_versions

    @abstractmethod
    def determine_version(self, request: HttpRequest, **kwargs: Any) -> str | None:
        """
        Determine the API version from the request.

        Args:
            request: The Django HTTP request
            **kwargs: Additional arguments (view, etc.)

        Returns:
            Version string or None
        """
        raise NotImplementedError("Subclasses must implement determine_version()")

    def is_allowed_version(self, version: str | None) -> bool:
        """
        Check if a version is in the allowed versions list.

        Args:
            version: Version string to check

        Returns:
            True if version is allowed
        """
        if self.allowed_versions is None:
            return True

        if version is None:
            return self.default_version is not None

        return version in self.allowed_versions

    def validate_version(self, version: str | None) -> str | None:
        """
        Validate and normalize a version string.

        Args:
            version: Version string to validate

        Returns:
            Normalized version string

        Raises:
            VersioningError: If version is not allowed
        """
        # Use default if no version specified
        if version is None:
            version = self.default_version

        # Check if allowed
        if not self.is_allowed_version(version):
            raise VersioningError(
                message=f"Invalid version '{version}'. Allowed versions: {self.allowed_versions}",
                version=version,
                allowed_versions=self.allowed_versions,
            )

        return version

    @staticmethod
    def parse_version(version: str) -> tuple[int, ...]:
        """
        Parse a version string into a tuple for comparison.

        Handles formats like "1", "1.0", "1.0.0", "v1", "v1.0".

        Args:
            version: Version string

        Returns:
            Tuple of version parts as integers
        """
        # Remove 'v' prefix if present
        version = version.lstrip("vV")

        # Split on dots and convert to integers
        parts = []
        for part in version.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                # Handle non-numeric parts (e.g., "1.0-beta")
                numeric = ""
                for char in part:
                    if char.isdigit():
                        numeric += char
                    else:
                        break
                parts.append(int(numeric) if numeric else 0)

        return tuple(parts)

    @classmethod
    def compare_versions(cls, v1: str, v2: str) -> int:
        """
        Compare two version strings.

        Args:
            v1: First version string
            v2: Second version string

        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        p1 = cls.parse_version(v1)
        p2 = cls.parse_version(v2)

        # Pad shorter tuple with zeros
        max_len = max(len(p1), len(p2))
        p1 = p1 + (0,) * (max_len - len(p1))
        p2 = p2 + (0,) * (max_len - len(p2))

        if p1 < p2:
            return -1
        if p1 > p2:
            return 1
        return 0

    def reverse(
        self,
        viewname: str,
        version: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Reverse a URL with version information.

        Subclasses should override this to include version in the URL.

        Args:
            viewname: The name of the view to reverse
            version: The version to include
            **kwargs: Additional arguments for URL reversing

        Returns:
            URL string with version
        """
        from django.urls import reverse

        return reverse(viewname, kwargs=kwargs)
