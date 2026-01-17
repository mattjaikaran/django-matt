"""
API Key models for SaaS API authentication.

Provides models for:
- API keys with live/test modes (like Stripe)
- Usage tracking for billing
- Rate limiting by plan tier
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class APIKeyManager(models.Manager):
    """Custom manager for API keys."""

    def get_by_key(self, key: str):
        """
        Get an API key by its full key value.
        Returns None if not found or inactive.
        """
        from .utils import hash_api_key, get_key_prefix

        key_hash = hash_api_key(key)
        prefix = get_key_prefix(key)

        try:
            return self.select_related("user").get(
                key_hash=key_hash,
                prefix=prefix,
                is_active=True,
            )
        except self.model.DoesNotExist:
            return None

    def get_valid(self, key: str):
        """
        Get a valid (active and not expired) API key.
        """
        api_key = self.get_by_key(key)
        if api_key is None:
            return None

        if api_key.is_expired:
            return None

        return api_key

    def active(self):
        """Get all active keys."""
        return self.filter(is_active=True)

    def live(self):
        """Get all live (non-test) keys."""
        return self.filter(is_active=True, is_test=False)

    def test(self):
        """Get all test keys."""
        return self.filter(is_active=True, is_test=True)


class APIKey(models.Model):
    """
    API Key for authenticating API requests.

    Supports:
    - Live and test keys (like Stripe's sk_live_ / sk_test_)
    - Scoped permissions
    - Expiration dates
    - Usage tracking
    - Rate limiting by plan tier

    Example:
        # Create a new API key
        key, raw_key = APIKey.objects.create_key(
            user=user,
            name="Production API Key",
            scopes=["read:users", "write:posts"],
        )
        # raw_key is only available at creation time

        # Validate a key from request
        api_key = APIKey.objects.get_valid(raw_key)
        if api_key:
            print(f"Authenticated as {api_key.user}")
    """

    # Key identification
    prefix = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Key prefix for identification (e.g., sk_live_abc123)",
    )
    key_hash = models.CharField(
        max_length=128,
        unique=True,
        help_text="SHA-256 hash of the full key",
    )

    # Owner
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text="User who owns this API key",
    )

    # Metadata
    name = models.CharField(
        max_length=100,
        help_text="User-friendly name for this key",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description",
    )

    # Key type
    is_test = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Test keys only work with test data",
    )

    # Permissions/Scopes
    scopes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of permission scopes (e.g., ['read:users', 'write:posts'])",
    )

    # Plan/Tier for rate limiting
    PLAN_FREE = "free"
    PLAN_STARTER = "starter"
    PLAN_PRO = "pro"
    PLAN_ENTERPRISE = "enterprise"
    PLAN_CHOICES = [
        (PLAN_FREE, "Free"),
        (PLAN_STARTER, "Starter"),
        (PLAN_PRO, "Pro"),
        (PLAN_ENTERPRISE, "Enterprise"),
    ]
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default=PLAN_FREE,
        help_text="Plan tier for rate limiting",
    )

    # Rate limits (requests per period)
    rate_limit = models.PositiveIntegerField(
        default=1000,
        help_text="Maximum requests per rate_limit_period",
    )
    rate_limit_period = models.PositiveIntegerField(
        default=3600,
        help_text="Rate limit period in seconds (default: 1 hour)",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive keys cannot authenticate",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Key expiration date (null = never expires)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this key was used",
    )

    # Usage tracking
    total_requests = models.PositiveBigIntegerField(
        default=0,
        help_text="Total number of requests made with this key",
    )

    # IP restrictions (optional)
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed IP addresses (empty = allow all)",
    )

    # Webhook signing (optional)
    webhook_secret = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Secret for signing webhooks to this customer",
    )

    objects = APIKeyManager()

    class Meta:
        db_table = "django_matt_api_keys"
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["key_hash"]),
            models.Index(fields=["prefix"]),
            models.Index(fields=["is_test", "is_active"]),
        ]

    def __str__(self):
        mode = "test" if self.is_test else "live"
        return f"{self.name} ({self.prefix}...) [{mode}]"

    @property
    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the key is valid (active and not expired)."""
        return self.is_active and not self.is_expired

    def has_scope(self, scope: str) -> bool:
        """
        Check if this key has a specific scope.

        Supports wildcards:
        - "*" matches everything
        - "read:*" matches "read:users", "read:posts", etc.
        """
        if not self.scopes:
            return True  # No scopes = full access

        if "*" in self.scopes:
            return True

        if scope in self.scopes:
            return True

        # Check for wildcard matches (e.g., "read:*" matches "read:users")
        scope_parts = scope.split(":")
        if len(scope_parts) == 2:
            wildcard = f"{scope_parts[0]}:*"
            if wildcard in self.scopes:
                return True

        return False

    def is_ip_allowed(self, ip: str) -> bool:
        """Check if an IP address is allowed to use this key."""
        if not self.allowed_ips:
            return True  # No restrictions
        return ip in self.allowed_ips

    def record_usage(self):
        """Record a usage of this key."""
        self.last_used_at = timezone.now()
        self.total_requests += 1
        self.save(update_fields=["last_used_at", "total_requests"])

    async def arecord_usage(self):
        """Async version of record_usage."""
        self.last_used_at = timezone.now()
        self.total_requests += 1
        await self.asave(update_fields=["last_used_at", "total_requests"])

    def revoke(self):
        """Revoke this API key."""
        self.is_active = False
        self.save(update_fields=["is_active"])

    async def arevoke(self):
        """Async version of revoke."""
        self.is_active = False
        await self.asave(update_fields=["is_active"])

    def get_rate_limit_key(self) -> str:
        """Get the cache key for rate limiting."""
        return f"api_key_rate_limit:{self.pk}"


class APIKeyUsage(models.Model):
    """
    Track API key usage for analytics and billing.

    Stores hourly aggregates of API usage per key.
    """

    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )

    # Time bucket (hourly)
    hour = models.DateTimeField(
        db_index=True,
        help_text="Start of the hour for this usage bucket",
    )

    # Request counts
    request_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of requests in this hour",
    )
    error_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of errors in this hour",
    )

    # Endpoint breakdown (JSON)
    endpoint_counts = models.JSONField(
        default=dict,
        help_text="Request counts by endpoint path",
    )

    # Response time stats
    avg_response_time_ms = models.FloatField(
        default=0,
        help_text="Average response time in milliseconds",
    )
    max_response_time_ms = models.FloatField(
        default=0,
        help_text="Maximum response time in milliseconds",
    )

    # Data transfer
    bytes_sent = models.PositiveBigIntegerField(
        default=0,
        help_text="Total bytes sent in responses",
    )
    bytes_received = models.PositiveBigIntegerField(
        default=0,
        help_text="Total bytes received in requests",
    )

    class Meta:
        db_table = "django_matt_api_key_usage"
        verbose_name = "API Key Usage"
        verbose_name_plural = "API Key Usage"
        ordering = ["-hour"]
        unique_together = [["api_key", "hour"]]
        indexes = [
            models.Index(fields=["api_key", "hour"]),
            models.Index(fields=["hour"]),
        ]

    def __str__(self):
        return f"{self.api_key.name} - {self.hour} ({self.request_count} requests)"

    @classmethod
    def record(
        cls,
        api_key: APIKey,
        endpoint: str,
        response_time_ms: float = 0,
        is_error: bool = False,
        bytes_sent: int = 0,
        bytes_received: int = 0,
    ):
        """
        Record a single API request.

        Uses get_or_create with update to handle concurrent requests.
        """
        now = timezone.now()
        hour = now.replace(minute=0, second=0, microsecond=0)

        usage, created = cls.objects.get_or_create(
            api_key=api_key,
            hour=hour,
            defaults={
                "request_count": 1,
                "error_count": 1 if is_error else 0,
                "endpoint_counts": {endpoint: 1},
                "avg_response_time_ms": response_time_ms,
                "max_response_time_ms": response_time_ms,
                "bytes_sent": bytes_sent,
                "bytes_received": bytes_received,
            },
        )

        if not created:
            # Update existing record
            usage.request_count += 1
            if is_error:
                usage.error_count += 1

            # Update endpoint counts
            endpoint_counts = usage.endpoint_counts or {}
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
            usage.endpoint_counts = endpoint_counts

            # Update response time stats
            if response_time_ms > 0:
                # Running average
                total = usage.avg_response_time_ms * (usage.request_count - 1)
                usage.avg_response_time_ms = (total + response_time_ms) / usage.request_count
                usage.max_response_time_ms = max(usage.max_response_time_ms, response_time_ms)

            usage.bytes_sent += bytes_sent
            usage.bytes_received += bytes_received
            usage.save()

        return usage


# Default rate limits by plan
PLAN_RATE_LIMITS = {
    APIKey.PLAN_FREE: {"rate_limit": 100, "rate_limit_period": 3600},  # 100/hour
    APIKey.PLAN_STARTER: {"rate_limit": 1000, "rate_limit_period": 3600},  # 1000/hour
    APIKey.PLAN_PRO: {"rate_limit": 10000, "rate_limit_period": 3600},  # 10000/hour
    APIKey.PLAN_ENTERPRISE: {"rate_limit": 100000, "rate_limit_period": 3600},  # 100000/hour
}
