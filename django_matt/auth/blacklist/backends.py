"""Token blacklist backends."""

from __future__ import annotations

import abc
from datetime import UTC, datetime

from django.core.cache import cache

from asgiref.sync import sync_to_async


class BaseBlacklistBackend(abc.ABC):
    """Abstract base class for blacklist backends."""

    @abc.abstractmethod
    def add(self, jti: str, expires_at: datetime) -> None:
        """Add a token JTI to the blacklist."""
        ...

    @abc.abstractmethod
    def check(self, jti: str) -> bool:
        """Check if a token JTI is blacklisted. Returns True if blacklisted."""
        ...

    @abc.abstractmethod
    def prune(self) -> int:
        """Remove expired entries. Returns the number of entries removed."""
        ...

    async def aadd(self, jti: str, expires_at: datetime) -> None:
        """Async version of add. Default wraps sync with sync_to_async."""
        await sync_to_async(self.add)(jti, expires_at)

    async def acheck(self, jti: str) -> bool:
        """Async version of check. Default wraps sync with sync_to_async."""
        return await sync_to_async(self.check)(jti)

    async def aprune(self) -> int:
        """Async version of prune. Default wraps sync with sync_to_async."""
        return await sync_to_async(self.prune)()


class NullBlacklistBackend(BaseBlacklistBackend):
    """No-op backend. Blacklisting is disabled; check() always returns False."""

    def add(self, jti: str, expires_at: datetime) -> None:
        return None

    def check(self, jti: str) -> bool:
        return False

    def prune(self) -> int:
        return 0

    async def aadd(self, jti: str, expires_at: datetime) -> None:
        return None

    async def acheck(self, jti: str) -> bool:
        return False

    async def aprune(self) -> int:
        return 0


class CacheBlacklistBackend(BaseBlacklistBackend):
    """Uses Django's cache framework to store blacklisted JTIs."""

    @property
    def _prefix(self) -> str:
        from .config import blacklist_config

        return blacklist_config.cache_prefix

    def _key(self, jti: str) -> str:
        return f"{self._prefix}{jti}"

    def add(self, jti: str, expires_at: datetime) -> None:
        ttl = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
        if ttl > 0:
            cache.set(self._key(jti), True, timeout=ttl)
        else:
            # Already expired, no need to store
            pass

    def check(self, jti: str) -> bool:
        return cache.get(self._key(jti)) is not None

    def prune(self) -> int:
        # Django cache handles expiry automatically; nothing to prune.
        return 0

    async def aadd(self, jti: str, expires_at: datetime) -> None:
        await sync_to_async(self.add)(jti, expires_at)

    async def acheck(self, jti: str) -> bool:
        return await sync_to_async(self.check)(jti)

    async def aprune(self) -> int:
        return 0


class DatabaseBlacklistBackend(BaseBlacklistBackend):
    """Uses the BlacklistedToken database model to store blacklisted JTIs."""

    def add(self, jti: str, expires_at: datetime) -> None:
        from .models import BlacklistedToken

        BlacklistedToken.objects.update_or_create(
            jti=jti,
            defaults={"expires_at": expires_at},
        )

    def check(self, jti: str) -> bool:
        from .models import BlacklistedToken

        return BlacklistedToken.objects.filter(
            jti=jti,
            expires_at__gt=datetime.now(UTC),
        ).exists()

    def prune(self) -> int:
        from .models import BlacklistedToken

        count, _ = BlacklistedToken.objects.filter(
            expires_at__lte=datetime.now(UTC),
        ).delete()
        return count

    async def aadd(self, jti: str, expires_at: datetime) -> None:
        from .models import BlacklistedToken

        await BlacklistedToken.objects.aupdate_or_create(
            jti=jti,
            defaults={"expires_at": expires_at},
        )

    async def acheck(self, jti: str) -> bool:
        from .models import BlacklistedToken

        return await BlacklistedToken.objects.filter(
            jti=jti,
            expires_at__gt=datetime.now(UTC),
        ).aexists()

    async def aprune(self) -> int:
        from .models import BlacklistedToken

        count, _ = await BlacklistedToken.objects.filter(
            expires_at__lte=datetime.now(UTC),
        ).adelete()
        return count
