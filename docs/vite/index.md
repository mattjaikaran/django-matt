# Vite Integration

Vite dev server HMR injection, build manifest parsing, and asset resolution for Django templates. Automatic hot module replacement during development, production-ready asset fingerprinting.

## Quick Start

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.vite.ViteDevMiddleware",
]

MATT_VITE = {
    "DEV_SERVER_URL": "http://localhost:5173",
    "BUILD_DIR": "static/dist",
    "MANIFEST_PATH": "static/dist/.vite/manifest.json",
    "ENTRY_POINTS": ["src/main.js"],
    "HMR_ENABLED": True,
    "REACT_REFRESH": False,
    "STATIC_URL_PREFIX": "/static/dist/",
}
```

## Configuration

```python
# settings.py
MATT_VITE = {
    "DEV_SERVER_URL": "http://localhost:5173",  # Vite dev server URL
    "BUILD_DIR": "static/dist",                  # Build output directory
    "MANIFEST_PATH": "static/dist/.vite/manifest.json",  # Manifest location
    "ENTRY_POINTS": ["src/main.js"],             # Vite entry points
    "HMR_ENABLED": True,                         # Enable HMR injection
    "REACT_REFRESH": False,                      # Enable React Fast Refresh
    "STATIC_URL_PREFIX": "/static/dist/",        # URL prefix for built assets
}
```

All settings have sensible defaults. The config is loaded once and cached.

## Key Features

### ViteDevMiddleware

Injects the Vite HMR client script into HTML responses during development:

```python
# Sync middleware
MIDDLEWARE = ["django_matt.vite.ViteDevMiddleware"]

# Async middleware (ASGI)
MIDDLEWARE = ["django_matt.vite.AsyncViteDevMiddleware"]
```

The middleware:
1. Only activates when `DEBUG=True`
2. Checks if the Vite dev server is reachable (socket check with 300ms timeout)
3. Injects `<script type="module" src="http://localhost:5173/@vite/client"></script>` before `</head>`
4. Optionally injects React Fast Refresh preamble when `REACT_REFRESH=True`

### ViteManifest

Parses the Vite build manifest to resolve entry points to hashed output files:

```python
from django_matt.vite.manifest import ViteManifest

manifest = ViteManifest()
manifest.load()  # Reads from MATT_VITE["MANIFEST_PATH"]

# Resolve an entry point
entry = manifest.resolve("src/main.js")
# ManifestEntry(file="assets/main-abc123.js", css=["assets/main-def456.css"], ...)

# Get script tags
tags = manifest.get_tags("src/main.js")

# Get all CSS for an entry (including transitive imports)
css_files = manifest.get_css("src/main.js")
```

`ManifestEntry` fields: `file`, `src`, `is_entry`, `css` (list), `imports` (list), `dynamic_imports` (list).

In development (`DEBUG=True`), the manifest reloads on every access. In production, it caches after the first load.

### ViteConfig

Access configuration programmatically:

```python
from django_matt.vite.config import get_vite_config, reset_vite_config

config = get_vite_config()
print(config.dev_server_url)   # "http://localhost:5173"
print(config.is_dev)           # True if DEBUG=True
print(config.entry_points)     # ["src/main.js"]

# Reset cached config (useful in tests)
reset_vite_config()
```

### Asset Fingerprinting

The `fingerprint` module handles cache-busting for production assets by appending content hashes to filenames.

## Practical Example

A Django template that works in both development and production:

```html
<!-- base.html -->
{% load vite %}
<!DOCTYPE html>
<html>
<head>
    {% vite_asset "src/main.js" %}
    {# In dev: loads from Vite dev server with HMR #}
    {# In prod: loads hashed files from manifest #}
</head>
<body>
    <div id="app"></div>
</body>
</html>
```

With React Fast Refresh:

```python
# settings.py
MATT_VITE = {
    "DEV_SERVER_URL": "http://localhost:5173",
    "REACT_REFRESH": True,  # Injects React Refresh preamble
    "ENTRY_POINTS": ["src/main.tsx"],
}
```

The middleware injects before `</head>`:

```html
<script type="module">
  import RefreshRuntime from "http://localhost:5173/@react-refresh";
  RefreshRuntime.injectIntoGlobalHook(window);
  window.$RefreshReg$ = () => {};
  window.$RefreshSig$ = () => (type) => type;
  window.__vite_plugin_react_preamble_installed__ = true;
</script>
<script type="module" src="http://localhost:5173/@vite/client"></script>
```
