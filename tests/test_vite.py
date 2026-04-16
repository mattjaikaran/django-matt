from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

import orjson
import pytest

from django_matt.vite.config import ViteConfig, get_vite_config, reset_vite_config
from django_matt.vite.manifest import (
    ManifestEntry,
    ViteManifest,
    get_manifest,
    reset_manifest,
)
from django_matt.vite.middleware import (
    AsyncViteDevMiddleware,
    ViteDevMiddleware,
    _inject_hmr_into_response,
    _is_vite_reachable,
)
from django_matt.vite.templatetags.vite import (
    vite_asset,
    vite_hmr_client,
    vite_preload,
    vite_react_refresh,
)

SAMPLE_MANIFEST = {
    "src/main.js": {
        "file": "assets/main-abc123.js",
        "src": "src/main.js",
        "isEntry": True,
        "css": ["assets/main-abc123.css"],
        "imports": ["_vendor-def456"],
    },
    "_vendor-def456": {
        "file": "assets/vendor-def456.js",
        "css": ["assets/vendor-def456.css"],
    },
    "src/styles.css": {
        "file": "assets/styles-789xyz.css",
        "src": "src/styles.css",
        "isEntry": True,
    },
}


@pytest.fixture(autouse=True)
def _clean_vite_state():
    reset_vite_config()
    reset_manifest()
    yield
    reset_vite_config()
    reset_manifest()


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    """Write a sample manifest.json and return its path."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(json.dumps(SAMPLE_MANIFEST).encode())
    return manifest_path


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


# ---------------------------------------------------------------------------
# ViteConfig
# ---------------------------------------------------------------------------


class TestViteConfig:
    def test_defaults(self):
        config = ViteConfig()
        assert config.dev_server_url == "http://localhost:5173"
        assert config.build_dir == "static/dist"
        assert config.manifest_path == "static/dist/.vite/manifest.json"
        assert config.entry_points == ["src/main.js"]
        assert config.hmr_enabled is True
        assert config.react_refresh is False
        assert config.static_url_prefix == "/static/dist/"

    @override_settings(MATT_VITE={
        "DEV_SERVER_URL": "http://localhost:3000",
        "BUILD_DIR": "frontend/build",
        "MANIFEST_PATH": "frontend/build/manifest.json",
        "ENTRY_POINTS": ["src/app.tsx"],
        "HMR_ENABLED": False,
        "REACT_REFRESH": True,
        "STATIC_URL_PREFIX": "/assets/",
    })
    def test_from_settings_custom(self):
        config = ViteConfig.from_settings()
        assert config.dev_server_url == "http://localhost:3000"
        assert config.build_dir == "frontend/build"
        assert config.manifest_path == "frontend/build/manifest.json"
        assert config.entry_points == ["src/app.tsx"]
        assert config.hmr_enabled is False
        assert config.react_refresh is True
        assert config.static_url_prefix == "/assets/"

    @override_settings(MATT_VITE={})
    def test_from_settings_empty_uses_defaults(self):
        config = ViteConfig.from_settings()
        assert config.dev_server_url == "http://localhost:5173"
        assert config.hmr_enabled is True

    def test_from_settings_no_setting(self):
        """No MATT_VITE in settings at all still produces defaults."""
        config = ViteConfig.from_settings()
        assert config.entry_points == ["src/main.js"]

    @override_settings(DEBUG=True)
    def test_is_dev_debug_true(self):
        config = ViteConfig()
        assert config.is_dev is True

    @override_settings(DEBUG=False)
    def test_is_dev_debug_false(self):
        config = ViteConfig()
        assert config.is_dev is False

    @override_settings(MATT_VITE={"DEV_SERVER_URL": "http://localhost:4000"})
    def test_partial_override(self):
        config = ViteConfig.from_settings()
        assert config.dev_server_url == "http://localhost:4000"
        # rest stays default
        assert config.hmr_enabled is True
        assert config.build_dir == "static/dist"


class TestViteConfigCaching:
    @override_settings(MATT_VITE={"DEV_SERVER_URL": "http://localhost:9999"})
    def test_get_vite_config_caches(self):
        c1 = get_vite_config()
        c2 = get_vite_config()
        assert c1 is c2
        assert c1.dev_server_url == "http://localhost:9999"

    def test_reset_clears_cache(self):
        c1 = get_vite_config()
        reset_vite_config()
        c2 = get_vite_config()
        assert c1 is not c2


# ---------------------------------------------------------------------------
# ManifestEntry
# ---------------------------------------------------------------------------


class TestManifestEntry:
    def test_defaults(self):
        entry = ManifestEntry(file="assets/foo.js")
        assert entry.file == "assets/foo.js"
        assert entry.src == ""
        assert entry.is_entry is False
        assert entry.css == []
        assert entry.imports == []
        assert entry.dynamic_imports == []


# ---------------------------------------------------------------------------
# ViteManifest
# ---------------------------------------------------------------------------


class TestViteManifest:
    def test_load_and_resolve(self, manifest_file: Path):
        m = ViteManifest()
        m.load(manifest_file)

        entry = m.resolve("src/main.js")
        assert entry is not None
        assert entry.file == "assets/main-abc123.js"
        assert entry.is_entry is True
        assert entry.css == ["assets/main-abc123.css"]
        assert entry.imports == ["_vendor-def456"]

    def test_resolve_missing_entry(self, manifest_file: Path):
        m = ViteManifest()
        m.load(manifest_file)
        assert m.resolve("nonexistent.js") is None

    def test_load_missing_file(self, tmp_path: Path):
        m = ViteManifest()
        m.load(tmp_path / "does_not_exist.json")
        assert m.resolve("src/main.js") is None

    def test_load_malformed_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        m = ViteManifest()
        with pytest.raises(orjson.JSONDecodeError):
            m.load(bad)

    def test_get_js_tags(self, manifest_file: Path):
        m = ViteManifest()
        m.load(manifest_file)
        tags = m.get_js_tags("src/main.js")
        assert len(tags) == 2
        # import chunk first
        assert "vendor-def456.js" in tags[0]
        assert 'type="module"' in tags[0]
        # main entry second
        assert "main-abc123.js" in tags[1]
        assert 'type="module"' in tags[1]

    def test_get_js_tags_missing_entry(self, manifest_file: Path):
        m = ViteManifest()
        m.load(manifest_file)
        assert m.get_js_tags("nope.js") == []

    def test_get_css_tags(self, manifest_file: Path):
        m = ViteManifest()
        m.load(manifest_file)
        tags = m.get_css_tags("src/main.js")
        # main's own CSS + vendor's CSS from import chain
        assert any("main-abc123.css" in t for t in tags)
        assert any("vendor-def456.css" in t for t in tags)
        for t in tags:
            assert 'rel="stylesheet"' in t

    def test_get_css_tags_no_css(self, manifest_file: Path):
        m = ViteManifest()
        m.load(manifest_file)
        # styles.css entry has no css list in manifest
        tags = m.get_css_tags("src/styles.css")
        assert tags == []

    def test_get_preload_tags(self, manifest_file: Path):
        m = ViteManifest()
        m.load(manifest_file)
        tags = m.get_preload_tags("src/main.js")
        assert len(tags) == 1
        assert 'rel="modulepreload"' in tags[0]
        assert "vendor-def456.js" in tags[0]

    def test_static_url_prefix_applied(self, manifest_file: Path):
        reset_vite_config()
        with override_settings(MATT_VITE={"STATIC_URL_PREFIX": "/cdn/"}):
            reset_vite_config()
            m = ViteManifest()
            m.load(manifest_file)
            tags = m.get_js_tags("src/main.js")
            assert all(t.startswith('<script type="module" src="/cdn/') for t in tags)

    def test_css_deduplication(self, tmp_path: Path):
        """Two import paths converging on same CSS should not duplicate."""
        manifest_data = {
            "src/app.js": {
                "file": "app.js",
                "isEntry": True,
                "css": ["shared.css"],
                "imports": ["_chunk"],
            },
            "_chunk": {
                "file": "chunk.js",
                "css": ["shared.css"],
            },
        }
        path = tmp_path / "manifest.json"
        path.write_bytes(json.dumps(manifest_data).encode())

        m = ViteManifest()
        m.load(path)
        tags = m.get_css_tags("src/app.js")
        # get_css_tags deduplicates
        hrefs = [t for t in tags if "shared.css" in t]
        assert len(hrefs) == 1

    def test_circular_imports(self, tmp_path: Path):
        """Circular import chains should not infinite-loop."""
        manifest_data = {
            "src/a.js": {
                "file": "a.js",
                "isEntry": True,
                "imports": ["_b"],
            },
            "_b": {
                "file": "b.js",
                "imports": ["src/a.js"],
            },
        }
        path = tmp_path / "manifest.json"
        path.write_bytes(json.dumps(manifest_data).encode())

        m = ViteManifest()
        m.load(path)
        # Should terminate without error
        tags = m.get_js_tags("src/a.js")
        assert len(tags) >= 1


class TestViteManifestSingleton:
    def test_get_manifest_returns_same_instance(self):
        m1 = get_manifest()
        m2 = get_manifest()
        assert m1 is m2

    def test_reset_manifest_clears(self):
        m1 = get_manifest()
        reset_manifest()
        m2 = get_manifest()
        assert m1 is not m2

    @override_settings(DEBUG=True)
    def test_dev_mode_reloads_manifest(self, manifest_file: Path):
        """In DEBUG mode, _ensure_loaded triggers reload every time."""
        m = ViteManifest()
        m.load(manifest_file)

        entry = m._entries.get("src/main.js")
        assert entry is not None

        # Overwrite manifest with new content
        new_data = {
            "src/app.tsx": {
                "file": "assets/app-new.js",
                "isEntry": True,
            }
        }
        manifest_file.write_bytes(json.dumps(new_data).encode())

        # Reload directly (in real use, _ensure_loaded does this via config path)
        m.load(manifest_file)
        assert m._entries.get("src/main.js") is None
        assert m._entries.get("src/app.tsx") is not None


# ---------------------------------------------------------------------------
# ViteDevMiddleware
# ---------------------------------------------------------------------------


class TestViteDevMiddleware:
    def _html_response(self, content: str = "<html><head></head><body></body></html>") -> HttpResponse:
        resp = HttpResponse(content, content_type="text/html")
        return resp

    def _json_response(self) -> HttpResponse:
        return HttpResponse('{"ok": true}', content_type="application/json")

    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": True})
    @patch("django_matt.vite.middleware._is_vite_reachable", return_value=True)
    def test_injects_hmr_script(self, mock_reachable: MagicMock, rf: RequestFactory):
        reset_vite_config()
        get_response = MagicMock(return_value=self._html_response())
        mw = ViteDevMiddleware(get_response)
        request = rf.get("/")
        response = mw(request)
        body = response.content.decode()
        assert "/@vite/client" in body
        assert 'type="module"' in body

    @override_settings(DEBUG=False, MATT_VITE={"HMR_ENABLED": True})
    def test_no_injection_in_production(self, rf: RequestFactory):
        reset_vite_config()
        get_response = MagicMock(return_value=self._html_response())
        mw = ViteDevMiddleware(get_response)
        request = rf.get("/")
        response = mw(request)
        body = response.content.decode()
        assert "/@vite/client" not in body

    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": False})
    def test_no_injection_when_hmr_disabled(self, rf: RequestFactory):
        reset_vite_config()
        get_response = MagicMock(return_value=self._html_response())
        mw = ViteDevMiddleware(get_response)
        request = rf.get("/")
        response = mw(request)
        body = response.content.decode()
        assert "/@vite/client" not in body

    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": True})
    @patch("django_matt.vite.middleware._is_vite_reachable", return_value=True)
    def test_skips_non_html(self, mock_reachable: MagicMock, rf: RequestFactory):
        reset_vite_config()
        get_response = MagicMock(return_value=self._json_response())
        mw = ViteDevMiddleware(get_response)
        request = rf.get("/api/data")
        response = mw(request)
        body = response.content.decode()
        assert "/@vite/client" not in body

    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": True})
    @patch("django_matt.vite.middleware._is_vite_reachable", return_value=False)
    def test_skips_when_vite_unreachable(self, mock_reachable: MagicMock, rf: RequestFactory):
        reset_vite_config()
        get_response = MagicMock(return_value=self._html_response())
        mw = ViteDevMiddleware(get_response)
        request = rf.get("/")
        response = mw(request)
        body = response.content.decode()
        assert "/@vite/client" not in body

    @override_settings(
        DEBUG=True,
        MATT_VITE={"HMR_ENABLED": True, "REACT_REFRESH": True},
    )
    @patch("django_matt.vite.middleware._is_vite_reachable", return_value=True)
    def test_injects_react_refresh(self, mock_reachable: MagicMock, rf: RequestFactory):
        reset_vite_config()
        get_response = MagicMock(return_value=self._html_response())
        mw = ViteDevMiddleware(get_response)
        request = rf.get("/")
        response = mw(request)
        body = response.content.decode()
        assert "@react-refresh" in body
        assert "RefreshRuntime" in body
        assert "__vite_plugin_react_preamble_installed__" in body

    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": True, "REACT_REFRESH": False})
    @patch("django_matt.vite.middleware._is_vite_reachable", return_value=True)
    def test_no_react_refresh_when_disabled(self, mock_reachable: MagicMock, rf: RequestFactory):
        reset_vite_config()
        get_response = MagicMock(return_value=self._html_response())
        mw = ViteDevMiddleware(get_response)
        request = rf.get("/")
        response = mw(request)
        body = response.content.decode()
        assert "@react-refresh" not in body


class TestInjectHmrIntoResponse:
    def test_inject_before_head_close(self):
        resp = HttpResponse("<html><head></head><body></body></html>", content_type="text/html")
        config = ViteConfig(dev_server_url="http://localhost:5173", react_refresh=False)
        _inject_hmr_into_response(resp, config)
        body = resp.content.decode()
        assert "/@vite/client" in body
        # script should appear before </head>
        idx_script = body.index("/@vite/client")
        idx_head = body.index("</head>")
        assert idx_script < idx_head

    def test_inject_fallback_to_body(self):
        resp = HttpResponse("<html><body>content</body></html>", content_type="text/html")
        config = ViteConfig(dev_server_url="http://localhost:5173", react_refresh=False)
        _inject_hmr_into_response(resp, config)
        body = resp.content.decode()
        assert "/@vite/client" in body

    def test_no_inject_without_head_or_body(self):
        resp = HttpResponse("<div>fragment</div>", content_type="text/html")
        config = ViteConfig(dev_server_url="http://localhost:5173", react_refresh=False)
        _inject_hmr_into_response(resp, config)
        body = resp.content.decode()
        assert "/@vite/client" not in body

    def test_content_length_updated(self):
        resp = HttpResponse("<html><head></head><body></body></html>", content_type="text/html")
        config = ViteConfig(dev_server_url="http://localhost:5173", react_refresh=False)
        _inject_hmr_into_response(resp, config)
        assert int(resp["Content-Length"]) == len(resp.content)

    def test_trailing_slash_stripped_from_dev_url(self):
        resp = HttpResponse("<html><head></head></html>", content_type="text/html")
        config = ViteConfig(dev_server_url="http://localhost:5173/", react_refresh=False)
        _inject_hmr_into_response(resp, config)
        body = resp.content.decode()
        assert "http://localhost:5173/@vite/client" in body
        assert "http://localhost:5173//@vite/client" not in body


class TestAsyncViteDevMiddleware:
    @pytest.mark.asyncio
    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": True})
    @patch("django_matt.vite.middleware._is_vite_reachable", return_value=True)
    async def test_async_injects_hmr(self, mock_reachable: MagicMock, rf: RequestFactory):
        reset_vite_config()
        resp = HttpResponse("<html><head></head><body></body></html>", content_type="text/html")

        async def async_get_response(request):
            return resp

        mw = AsyncViteDevMiddleware(async_get_response)
        request = rf.get("/")
        response = await mw(request)
        body = response.content.decode()
        assert "/@vite/client" in body

    @pytest.mark.asyncio
    @override_settings(DEBUG=False)
    async def test_async_no_injection_production(self, rf: RequestFactory):
        reset_vite_config()
        resp = HttpResponse("<html><head></head></html>", content_type="text/html")

        async def async_get_response(request):
            return resp

        mw = AsyncViteDevMiddleware(async_get_response)
        request = rf.get("/")
        response = await mw(request)
        body = response.content.decode()
        assert "/@vite/client" not in body


class TestIsViteReachable:
    @patch("django_matt.vite.middleware.socket.create_connection")
    def test_reachable(self, mock_conn: MagicMock):
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        assert _is_vite_reachable("http://localhost:5173") is True

    @patch("django_matt.vite.middleware.socket.create_connection", side_effect=OSError)
    def test_unreachable(self, mock_conn: MagicMock):
        assert _is_vite_reachable("http://localhost:5173") is False

    @patch("django_matt.vite.middleware.socket.create_connection")
    def test_parses_custom_port(self, mock_conn: MagicMock):
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        _is_vite_reachable("http://127.0.0.1:3000")
        mock_conn.assert_called_once_with(("127.0.0.1", 3000), timeout=0.3)


# ---------------------------------------------------------------------------
# Template tags
# ---------------------------------------------------------------------------


class TestViteAssetTag:
    @override_settings(DEBUG=True, MATT_VITE={"DEV_SERVER_URL": "http://localhost:5173"})
    def test_dev_mode_renders_dev_url(self):
        reset_vite_config()
        output = vite_asset("src/main.js")
        assert 'src="http://localhost:5173/src/main.js"' in output
        assert 'type="module"' in output

    @override_settings(DEBUG=False, MATT_VITE={"STATIC_URL_PREFIX": "/static/dist/"})
    def test_prod_mode_renders_from_manifest(self, manifest_file: Path):
        reset_vite_config()
        m = ViteManifest()
        m.load(manifest_file)
        with patch("django_matt.vite.templatetags.vite.get_manifest", return_value=m):
            output = vite_asset("src/main.js")
            assert "main-abc123.js" in output
            assert "main-abc123.css" in output

    @override_settings(DEBUG=False, MATT_VITE={"STATIC_URL_PREFIX": "/static/dist/"})
    def test_prod_missing_entry_renders_empty(self, manifest_file: Path):
        reset_vite_config()
        m = ViteManifest()
        m.load(manifest_file)
        with patch("django_matt.vite.templatetags.vite.get_manifest", return_value=m):
            output = vite_asset("nonexistent.js")
            assert output.strip() == ""


class TestViteHmrClientTag:
    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": True, "DEV_SERVER_URL": "http://localhost:5173"})
    def test_dev_mode_renders_client(self):
        reset_vite_config()
        output = vite_hmr_client()
        assert "/@vite/client" in output

    @override_settings(DEBUG=False)
    def test_prod_mode_empty(self):
        reset_vite_config()
        output = vite_hmr_client()
        assert output == ""

    @override_settings(DEBUG=True, MATT_VITE={"HMR_ENABLED": False})
    def test_hmr_disabled_empty(self):
        reset_vite_config()
        output = vite_hmr_client()
        assert output == ""


class TestViteReactRefreshTag:
    @override_settings(DEBUG=True, MATT_VITE={"REACT_REFRESH": True, "DEV_SERVER_URL": "http://localhost:5173"})
    def test_renders_preamble(self):
        reset_vite_config()
        output = vite_react_refresh()
        assert "@react-refresh" in output
        assert "RefreshRuntime" in output
        assert "__vite_plugin_react_preamble_installed__" in output

    @override_settings(DEBUG=True, MATT_VITE={"REACT_REFRESH": False})
    def test_disabled_empty(self):
        reset_vite_config()
        output = vite_react_refresh()
        assert output == ""

    @override_settings(DEBUG=False, MATT_VITE={"REACT_REFRESH": True})
    def test_prod_mode_empty(self):
        reset_vite_config()
        output = vite_react_refresh()
        assert output == ""


class TestVitePreloadTag:
    @override_settings(DEBUG=True)
    def test_dev_mode_empty(self):
        reset_vite_config()
        output = vite_preload("src/main.js")
        assert output == ""

    @override_settings(DEBUG=False, MATT_VITE={"STATIC_URL_PREFIX": "/static/dist/"})
    def test_prod_renders_preload(self, manifest_file: Path):
        reset_vite_config()
        m = ViteManifest()
        m.load(manifest_file)
        with patch("django_matt.vite.templatetags.vite.get_manifest", return_value=m):
            output = vite_preload("src/main.js")
            assert 'rel="modulepreload"' in output
            assert "vendor-def456.js" in output


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_manifest(self, tmp_path: Path):
        path = tmp_path / "manifest.json"
        path.write_bytes(b"{}")
        m = ViteManifest()
        m.load(path)
        assert m.resolve("anything") is None
        assert m.get_js_tags("anything") == []
        assert m.get_css_tags("anything") == []

    def test_manifest_entry_with_no_optional_fields(self, tmp_path: Path):
        data = {"src/index.js": {"file": "index-hash.js"}}
        path = tmp_path / "manifest.json"
        path.write_bytes(json.dumps(data).encode())
        m = ViteManifest()
        m.load(path)
        entry = m.resolve("src/index.js")
        assert entry is not None
        assert entry.file == "index-hash.js"
        assert entry.css == []
        assert entry.imports == []
        assert entry.is_entry is False

    def test_deep_import_chain(self, tmp_path: Path):
        """3-level deep import chain resolves all chunks."""
        data = {
            "src/app.js": {
                "file": "app.js",
                "isEntry": True,
                "imports": ["_a"],
            },
            "_a": {"file": "a.js", "imports": ["_b"]},
            "_b": {"file": "b.js", "imports": ["_c"]},
            "_c": {"file": "c.js"},
        }
        path = tmp_path / "manifest.json"
        path.write_bytes(json.dumps(data).encode())
        m = ViteManifest()
        m.load(path)
        tags = m.get_js_tags("src/app.js")
        files = [t.split('src="')[1].split('"')[0] for t in tags]
        # All chunks + main entry
        assert len(tags) == 4
        assert files[-1].endswith("app.js")

    @override_settings(MATT_VITE={"DEV_SERVER_URL": "http://localhost:5173/"})
    def test_dev_url_trailing_slash_normalization(self):
        reset_vite_config()
        config = get_vite_config()
        # The code strips trailing slash via .rstrip("/")
        url = config.dev_server_url.rstrip("/")
        assert url == "http://localhost:5173"

    def test_manifest_thread_safety(self, manifest_file: Path):
        """Concurrent loads should not corrupt state."""
        import concurrent.futures

        m = ViteManifest()

        def load_and_resolve():
            m.load(manifest_file)
            return m.resolve("src/main.js")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(load_and_resolve) for _ in range(20)]
            results = [f.result() for f in futures]

        # All should resolve successfully
        assert all(r is not None for r in results)
        assert all(r.file == "assets/main-abc123.js" for r in results)
