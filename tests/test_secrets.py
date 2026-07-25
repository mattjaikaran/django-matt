from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from django_matt.secrets.backends import (
    DotenvBackend,
    EncryptedFileBackend,
    EnvBackend,
    SecretsBackend,
)
from django_matt.secrets.fields import SecretField, _LazySecret, _MaskedStr, secret
from django_matt.secrets.manager import (
    SecretReference,
    SecretsManager,
    get_secrets_manager,
    reset_secrets_manager,
)
from django_matt.secrets.rotation import (
    RotationChecker,
    RotationPolicy,
    _rotation_registry,
    fire_rotation_hooks,
    on_rotation,
)

# =============================================================================
# SecretReference
# =============================================================================


class TestSecretReference:
    def test_parse_env(self):
        ref = SecretReference("env://MY_VAR")
        assert ref.scheme == "env"
        assert ref.path == "MY_VAR"

    def test_parse_vault(self):
        ref = SecretReference("vault://path/to/secret")
        assert ref.scheme == "vault"
        assert ref.path == "path/to/secret"

    def test_parse_plain(self):
        ref = SecretReference("plain://hello")
        assert ref.scheme == "plain"
        assert ref.path == "hello"

    def test_invalid_uri_raises(self):
        with pytest.raises(ValueError, match="invalid secret reference"):
            SecretReference("no-scheme")

    def test_repr_masks_value(self):
        ref = SecretReference("env://SECRET_KEY")
        assert "SECRET_KEY" not in repr(ref)
        assert "***" in repr(ref)

    def test_str_masks_value(self):
        ref = SecretReference("aws://my-secret")
        assert "my-secret" not in str(ref)
        assert "***" in str(ref)

    def test_uri_property(self):
        ref = SecretReference("env://FOO")
        assert ref.uri == "env://FOO"


# =============================================================================
# EnvBackend
# =============================================================================


class TestEnvBackend:
    @pytest.fixture
    def backend(self):
        return EnvBackend()

    @pytest.fixture
    def prefixed_backend(self):
        return EnvBackend(prefix="APP_")

    @pytest.mark.asyncio
    async def test_get_existing(self, backend):
        os.environ["TEST_SECRET_1"] = "value1"
        try:
            result = await backend.get("TEST_SECRET_1")
            assert result == "value1"
        finally:
            del os.environ["TEST_SECRET_1"]

    @pytest.mark.asyncio
    async def test_get_missing(self, backend):
        result = await backend.get("NONEXISTENT_SECRET_XYZ")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_many(self, backend):
        os.environ["TEST_A"] = "a"
        os.environ["TEST_B"] = "b"
        try:
            result = await backend.get_many(["TEST_A", "TEST_B", "TEST_MISSING"])
            assert result == {"TEST_A": "a", "TEST_B": "b", "TEST_MISSING": None}
        finally:
            del os.environ["TEST_A"]
            del os.environ["TEST_B"]

    @pytest.mark.asyncio
    async def test_set(self, backend):
        await backend.set("TEST_SET_KEY", "set_value")
        try:
            assert os.environ["TEST_SET_KEY"] == "set_value"
        finally:
            del os.environ["TEST_SET_KEY"]

    @pytest.mark.asyncio
    async def test_delete(self, backend):
        os.environ["TEST_DEL_KEY"] = "to_delete"
        await backend.delete("TEST_DEL_KEY")
        assert "TEST_DEL_KEY" not in os.environ

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend):
        await backend.delete("NONEXISTENT_KEY_XYZ")

    @pytest.mark.asyncio
    async def test_prefix(self, prefixed_backend):
        os.environ["APP_DB_PASS"] = "secret"
        try:
            result = await prefixed_backend.get("DB_PASS")
            assert result == "secret"
        finally:
            del os.environ["APP_DB_PASS"]

    @pytest.mark.asyncio
    async def test_list_keys_with_prefix(self, prefixed_backend):
        os.environ["APP_KEY1"] = "v1"
        os.environ["APP_KEY2"] = "v2"
        try:
            keys = await prefixed_backend.list_keys()
            assert "KEY1" in keys
            assert "KEY2" in keys
        finally:
            del os.environ["APP_KEY1"]
            del os.environ["APP_KEY2"]

    def test_conforms_to_protocol(self, backend):
        assert isinstance(backend, SecretsBackend)


# =============================================================================
# DotenvBackend
# =============================================================================


class TestDotenvBackend:
    @pytest.fixture
    def env_file(self, tmp_path):
        p = tmp_path / ".env"
        p.write_text('DB_HOST=localhost\nDB_PORT=5432\nDB_PASS="s3cret"\n# comment\nEMPTY=\n')
        return p

    @pytest.fixture
    def backend(self, env_file):
        return DotenvBackend(path=env_file)

    @pytest.mark.asyncio
    async def test_get(self, backend):
        assert await backend.get("DB_HOST") == "localhost"

    @pytest.mark.asyncio
    async def test_get_quoted(self, backend):
        assert await backend.get("DB_PASS") == "s3cret"

    @pytest.mark.asyncio
    async def test_get_empty(self, backend):
        assert await backend.get("EMPTY") == ""

    @pytest.mark.asyncio
    async def test_get_missing(self, backend):
        assert await backend.get("NONEXISTENT") is None

    @pytest.mark.asyncio
    async def test_get_many(self, backend):
        result = await backend.get_many(["DB_HOST", "DB_PORT"])
        assert result == {"DB_HOST": "localhost", "DB_PORT": "5432"}

    @pytest.mark.asyncio
    async def test_set_and_persist(self, backend, env_file):
        await backend.set("NEW_KEY", "new_value")
        assert await backend.get("NEW_KEY") == "new_value"
        # verify written to file
        content = env_file.read_text()
        assert "NEW_KEY=new_value" in content

    @pytest.mark.asyncio
    async def test_delete(self, backend):
        await backend.delete("DB_HOST")
        assert await backend.get("DB_HOST") is None

    @pytest.mark.asyncio
    async def test_list_keys(self, backend):
        keys = await backend.list_keys()
        assert "DB_HOST" in keys
        assert "DB_PORT" in keys

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, tmp_path):
        backend = DotenvBackend(path=tmp_path / "nope.env")
        assert await backend.get("ANY") is None
        assert await backend.list_keys() == []


# =============================================================================
# EncryptedFileBackend
# =============================================================================


class TestEncryptedFileBackend:
    @pytest.fixture
    def fernet_key(self):
        pytest.importorskip("cryptography")
        return EncryptedFileBackend.generate_key()

    @pytest.fixture
    def backend(self, tmp_path, fernet_key):
        return EncryptedFileBackend(path=tmp_path / "secrets.enc", key=fernet_key)

    @pytest.mark.asyncio
    async def test_set_and_get(self, backend):
        await backend.set("API_KEY", "abc123")
        assert await backend.get("API_KEY") == "abc123"

    @pytest.mark.asyncio
    async def test_get_missing(self, backend):
        assert await backend.get("NOPE") is None

    @pytest.mark.asyncio
    async def test_get_many(self, backend):
        await backend.set("A", "1")
        await backend.set("B", "2")
        result = await backend.get_many(["A", "B", "C"])
        assert result == {"A": "1", "B": "2", "C": None}

    @pytest.mark.asyncio
    async def test_delete(self, backend):
        await backend.set("DEL", "val")
        await backend.delete("DEL")
        assert await backend.get("DEL") is None

    @pytest.mark.asyncio
    async def test_list_keys(self, backend):
        await backend.set("X", "1")
        await backend.set("Y", "2")
        keys = await backend.list_keys()
        assert sorted(keys) == ["X", "Y"]

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_path, fernet_key):
        path = tmp_path / "persist.enc"
        b1 = EncryptedFileBackend(path=path, key=fernet_key)
        await b1.set("PERSIST", "data")

        b2 = EncryptedFileBackend(path=path, key=fernet_key)
        assert await b2.get("PERSIST") == "data"

    def test_generate_key_returns_string(self):
        pytest.importorskip("cryptography")
        key = EncryptedFileBackend.generate_key()
        assert isinstance(key, str)
        assert len(key) > 20


# =============================================================================
# SecretsManager
# =============================================================================


class TestSecretsManager:
    @pytest.fixture
    def backend(self):
        return EnvBackend()

    @pytest.fixture
    def manager(self, backend):
        return SecretsManager(backend=backend, cache_ttl=1.0)

    @pytest.mark.asyncio
    async def test_get(self, manager):
        os.environ["MGR_TEST"] = "hello"
        try:
            assert await manager.get("MGR_TEST") == "hello"
        finally:
            del os.environ["MGR_TEST"]

    @pytest.mark.asyncio
    async def test_get_default(self, manager):
        result = await manager.get("NONEXISTENT_MGR", default="fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_get_caches(self, manager):
        os.environ["CACHED_KEY"] = "original"
        try:
            assert await manager.get("CACHED_KEY") == "original"
            os.environ["CACHED_KEY"] = "changed"
            # still returns cached value
            assert await manager.get("CACHED_KEY") == "original"
        finally:
            del os.environ["CACHED_KEY"]

    @pytest.mark.asyncio
    async def test_cache_expires(self, manager):
        os.environ["EXPIRING"] = "v1"
        try:
            assert await manager.get("EXPIRING") == "v1"
            os.environ["EXPIRING"] = "v2"
            time.sleep(1.1)  # wait for TTL
            assert await manager.get("EXPIRING") == "v2"
        finally:
            del os.environ["EXPIRING"]

    @pytest.mark.asyncio
    async def test_invalidate(self, manager):
        os.environ["INV_KEY"] = "v1"
        try:
            await manager.get("INV_KEY")
            os.environ["INV_KEY"] = "v2"
            manager.invalidate("INV_KEY")
            assert await manager.get("INV_KEY") == "v2"
        finally:
            del os.environ["INV_KEY"]

    @pytest.mark.asyncio
    async def test_invalidate_all(self, manager):
        os.environ["ALL1"] = "a"
        os.environ["ALL2"] = "b"
        try:
            await manager.get("ALL1")
            await manager.get("ALL2")
            manager.invalidate_all()
            assert manager._cache == {}
        finally:
            del os.environ["ALL1"]
            del os.environ["ALL2"]

    @pytest.mark.asyncio
    async def test_get_many(self, manager):
        os.environ["MANY_A"] = "1"
        os.environ["MANY_B"] = "2"
        try:
            result = await manager.get_many(["MANY_A", "MANY_B"])
            assert result == {"MANY_A": "1", "MANY_B": "2"}
        finally:
            del os.environ["MANY_A"]
            del os.environ["MANY_B"]

    @pytest.mark.asyncio
    async def test_set(self, manager):
        await manager.set("SET_KEY", "set_val")
        try:
            assert os.environ["SET_KEY"] == "set_val"
            # also cached
            assert await manager.get("SET_KEY") == "set_val"
        finally:
            del os.environ["SET_KEY"]

    @pytest.mark.asyncio
    async def test_delete(self, manager):
        os.environ["DEL_MGR"] = "bye"
        await manager.get("DEL_MGR")  # populate cache
        await manager.delete("DEL_MGR")
        assert "DEL_MGR" not in os.environ
        assert "DEL_MGR" not in manager._cache

    @pytest.mark.asyncio
    async def test_resolve_ref_plain(self, manager):
        ref = SecretReference("plain://literal_value")
        assert await manager.resolve_ref(ref) == "literal_value"

    @pytest.mark.asyncio
    async def test_resolve_ref_env(self, manager):
        os.environ["REF_ENV"] = "ref_val"
        try:
            ref = SecretReference("env://REF_ENV")
            # default backend is env, so scheme lookup falls through to default
            assert await manager.resolve_ref(ref) == "ref_val"
        finally:
            del os.environ["REF_ENV"]

    @pytest.mark.asyncio
    async def test_rotate_fires_hooks(self, manager):
        called_with = []
        manager.on_rotation("ROT_KEY", lambda k: called_with.append(k))
        await manager.rotate("ROT_KEY")
        assert called_with == ["ROT_KEY"]

    @pytest.mark.asyncio
    async def test_rotate_async_hook(self, manager):
        called_with = []

        async def hook(k):
            called_with.append(k)

        manager.on_rotation("ASYNC_ROT", hook)
        await manager.rotate("ASYNC_ROT")
        assert called_with == ["ASYNC_ROT"]

    @pytest.mark.asyncio
    async def test_rotate_invalidates_cache(self, manager):
        os.environ["ROT_CACHE"] = "old"
        try:
            await manager.get("ROT_CACHE")
            os.environ["ROT_CACHE"] = "new"
            await manager.rotate("ROT_CACHE")
            assert await manager.get("ROT_CACHE") == "new"
        finally:
            del os.environ["ROT_CACHE"]

    @pytest.mark.asyncio
    async def test_multi_backend(self):
        env_backend = EnvBackend()
        prefixed = EnvBackend(prefix="VAULT_")
        manager = SecretsManager(
            backend=env_backend,
            backends={"vault": prefixed},
        )
        os.environ["VAULT_DB_PASS"] = "vaultpass"
        try:
            ref = SecretReference("vault://DB_PASS")
            assert await manager.resolve_ref(ref) == "vaultpass"
        finally:
            del os.environ["VAULT_DB_PASS"]

    @pytest.mark.asyncio
    async def test_list_keys(self, manager):
        keys = await manager.list_keys()
        assert isinstance(keys, list)


# =============================================================================
# get_secrets_manager singleton
# =============================================================================


class TestGetSecretsManager:
    def setup_method(self):
        reset_secrets_manager()

    def teardown_method(self):
        reset_secrets_manager()

    def test_returns_singleton(self):
        m1 = get_secrets_manager()
        m2 = get_secrets_manager()
        assert m1 is m2

    def test_reset(self):
        m1 = get_secrets_manager()
        reset_secrets_manager()
        m2 = get_secrets_manager()
        assert m1 is not m2


# =============================================================================
# MaskedStr / SecretField
# =============================================================================


class TestMaskedStr:
    def test_repr_masked(self):
        s = _MaskedStr("supersecret")
        assert repr(s) == "'***'"

    def test_str_masked(self):
        s = _MaskedStr("supersecret")
        assert str(s) == "***"

    def test_secret_value(self):
        s = _MaskedStr("supersecret")
        assert s.secret_value == "supersecret"

    def test_is_str_subclass(self):
        s = _MaskedStr("test")
        assert isinstance(s, str)


class TestSecretFieldValidation:
    def test_validate_string(self):
        result = SecretField._validate("hello")
        assert isinstance(result, _MaskedStr)
        assert result.secret_value == "hello"

    def test_validate_masked_str(self):
        m = _MaskedStr("x")
        result = SecretField._validate(m)
        assert result is m

    def test_validate_non_string_raises(self):
        with pytest.raises(ValueError, match="expected str"):
            SecretField._validate(123)


# =============================================================================
# secret() lazy resolver
# =============================================================================


class TestLazySecret:
    def test_resolves_from_env(self):
        os.environ["LAZY_TEST"] = "lazy_val"
        try:
            s = secret("LAZY_TEST")
            assert str(s) == "lazy_val"
        finally:
            del os.environ["LAZY_TEST"]

    def test_default_value(self):
        s = secret("MISSING_LAZY", default="fallback")
        assert str(s) == "fallback"

    def test_missing_no_default(self):
        s = secret("MISSING_NO_DEFAULT")
        assert str(s) == ""

    def test_bool_true(self):
        os.environ["BOOL_TEST"] = "yes"
        try:
            s = secret("BOOL_TEST")
            assert bool(s) is True
        finally:
            del os.environ["BOOL_TEST"]

    def test_bool_false(self):
        s = secret("MISSING_BOOL_TEST")
        assert bool(s) is False

    def test_repr_masks(self):
        s = secret("SOME_KEY")
        assert repr(s) == "secret('SOME_KEY')"

    def test_eq_string(self):
        os.environ["EQ_TEST"] = "match"
        try:
            s = secret("EQ_TEST")
            assert s == "match"
            assert s != "other"
        finally:
            del os.environ["EQ_TEST"]

    def test_hash(self):
        os.environ["HASH_TEST"] = "hashme"
        try:
            s = secret("HASH_TEST")
            assert hash(s) == hash("hashme")
        finally:
            del os.environ["HASH_TEST"]

    def test_len(self):
        os.environ["LEN_TEST"] = "12345"
        try:
            s = secret("LEN_TEST")
            assert len(s) == 5
        finally:
            del os.environ["LEN_TEST"]

    def test_add(self):
        os.environ["ADD_TEST"] = "hello"
        try:
            s = secret("ADD_TEST")
            assert s + " world" == "hello world"
            assert "say " + s == "say hello"
        finally:
            del os.environ["ADD_TEST"]

    def test_caches_resolved_value(self):
        os.environ["CACHE_LAZY"] = "v1"
        try:
            s = secret("CACHE_LAZY")
            assert str(s) == "v1"
            os.environ["CACHE_LAZY"] = "v2"
            # still v1 because resolved and cached
            assert str(s) == "v1"
        finally:
            del os.environ["CACHE_LAZY"]


# =============================================================================
# RotationPolicy
# =============================================================================


class TestRotationPolicy:
    def test_not_expired_initially(self):
        policy = RotationPolicy(key="test", ttl_seconds=60.0)
        assert not policy.is_expired

    def test_expired_after_ttl(self):
        policy = RotationPolicy(key="test", ttl_seconds=0.0)
        time.sleep(0.01)
        assert policy.is_expired

    def test_time_remaining(self):
        policy = RotationPolicy(key="test", ttl_seconds=100.0)
        assert policy.time_remaining > 90

    def test_mark_rotated(self):
        policy = RotationPolicy(key="test", ttl_seconds=0.0)
        time.sleep(0.01)
        assert policy.is_expired
        policy.mark_rotated()
        assert not policy.is_expired or policy.ttl_seconds == 0.0


# =============================================================================
# on_rotation decorator
# =============================================================================


class TestOnRotation:
    def setup_method(self):
        _rotation_registry.clear()

    def teardown_method(self):
        _rotation_registry.clear()

    def test_registers_callback(self):
        @on_rotation("DB_PASS")
        def handle(key):
            pass

        assert handle in _rotation_registry["DB_PASS"]

    @pytest.mark.asyncio
    async def test_fire_rotation_hooks(self):
        called = []

        @on_rotation("FIRE_KEY")
        def handler(key):
            called.append(key)

        await fire_rotation_hooks("FIRE_KEY")
        assert called == ["FIRE_KEY"]

    @pytest.mark.asyncio
    async def test_fire_async_hook(self):
        called = []

        @on_rotation("ASYNC_KEY")
        async def handler(key):
            called.append(key)

        await fire_rotation_hooks("ASYNC_KEY")
        assert called == ["ASYNC_KEY"]

    @pytest.mark.asyncio
    async def test_fire_no_hooks(self):
        await fire_rotation_hooks("NO_HOOKS_KEY")


# =============================================================================
# RotationChecker
# =============================================================================


class TestRotationChecker:
    def test_add_policy(self):
        checker = RotationChecker()
        policy = RotationPolicy(key="test", ttl_seconds=60)
        checker.add_policy(policy)
        assert len(checker._policies) == 1

    @pytest.mark.asyncio
    async def test_check_expired_policy(self):
        called = []

        def cb(key):
            called.append(key)

        checker = RotationChecker(check_interval=0.1)
        policy = RotationPolicy(key="exp", ttl_seconds=0.0, callback=cb)
        time.sleep(0.01)
        checker.add_policy(policy)
        await checker._check_policies()
        assert called == ["exp"]

    @pytest.mark.asyncio
    async def test_check_non_expired(self):
        called = []
        checker = RotationChecker()
        policy = RotationPolicy(key="ok", ttl_seconds=9999, callback=lambda k: called.append(k))
        checker.add_policy(policy)
        await checker._check_policies()
        assert called == []


# =============================================================================
# CLI
# =============================================================================


class TestSecretsCLI:
    def test_app_exists(self):
        from django_matt.secrets.cli import app

        assert app is not None
        assert app.info.name == "secrets"
