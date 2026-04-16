# SDK Reference Schema

`openapi.json` in this directory is the canonical API schema the release
workflow (`.github/workflows/release.yml`) compiles into TypeScript / Python /
Swift client SDKs via `scripts/generate_sdks.py`.

Regenerate it whenever the public surface of the framework changes by booting
a representative django-matt app and dumping its OpenAPI document:

```bash
uv run python manage.py build_openapi --output sdk-reference/openapi.json
# or, if you have a running dev server:
curl http://localhost:8000/openapi.json > sdk-reference/openapi.json
```

The release pipeline publishes:

- `django-matt-client` on npm (TypeScript)
- `django-matt-client` on PyPI (Python)
- A Swift SDK tarball attached to the GitHub release (consumed via SwiftPM git URL)

All three SDKs are versioned in lockstep with the framework — the release tag
(`vX.Y.Z`) becomes the SDK version.
