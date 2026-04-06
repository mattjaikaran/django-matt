# HTTP Header Parser

## What It Is

A Rust-compiled parser that extracts and structures common HTTP headers from Django's `request.META` dict. Replaces multiple string operations (splits, lookups, conditional checks) with one native call.

## Why It Exists

Every authenticated request needs to extract the `Authorization` header, split it into type and credential, and validate the type. API key middleware does the same for `X-API-Key`. Content negotiation needs to parse `Accept` with quality values. Each of these is a few string operations in Python, but they add up:

```python
# What Python does per-request (simplified):
auth = request.META.get("HTTP_AUTHORIZATION", "")
parts = auth.split()           # allocation + split
if len(parts) == 2:
    auth_type, token = parts   # tuple unpack
    if auth_type in valid_types:  # set lookup
        return token

api_key = request.META.get("HTTP_X_API_KEY")  # another lookup
request_id = request.META.get("HTTP_X_REQUEST_ID")  # another
# ... Accept header parsing with quality values ...
```

The Rust parser does all of this in one call, returning a structured dict that both JWT middleware and API key middleware can read from.

## How It Works

```python
from django_matt._accel import parse_headers_rust

meta = {
    "HTTP_AUTHORIZATION": "Bearer eyJhbGci...",
    "HTTP_ACCEPT": "application/json;q=1.0, text/html;q=0.5",
    "CONTENT_TYPE": "application/json; charset=utf-8",
    "HTTP_X_REQUEST_ID": "req-abc-123",
    "HTTP_X_API_KEY": "sk_live_test123",
}

result = parse_headers_rust(meta)
# {
#     "authorization": {"type": "Bearer", "credential": "eyJhbGci..."},
#     "api_key": "sk_live_test123",
#     "request_id": "req-abc-123",
#     "content_type": {"media_type": "application/json", "params": "charset=utf-8"},
#     "accept": {"application/json": 1.0, "text/html": 0.5},
# }
```

### Parsed headers:

| Header | META Key | Output |
|--------|----------|--------|
| `Authorization` | `HTTP_AUTHORIZATION` | `{"type": "Bearer", "credential": "..."}` |
| `X-API-Key` | `HTTP_X_API_KEY` | string |
| `X-Request-ID` | `HTTP_X_REQUEST_ID` | string |
| `Content-Type` | `CONTENT_TYPE` | `{"media_type": "...", "params": "..."}` |
| `Accept` | `HTTP_ACCEPT` | `{media_type: quality_float}` |

### Edge cases:

- **Malformed Authorization** (no space, e.g., `"BearerTokenWithoutSpace"`) — the authorization key is omitted entirely. This matches Django's behavior of requiring `<type> <credential>` format.
- **Accept quality values** — parsed as `f64`, defaults to `1.0` for entries without `;q=`
- **Missing headers** — keys are simply absent from the result dict

## Where It's Used

### JWT Authentication

`django_matt/auth/jwt.py` — `get_token_from_request()`:

```python
parsed = _get_parsed_headers(request)  # Rust parse + cache on request
if parsed is not None:
    auth = parsed.get("authorization")
    if auth and auth["type"] in jwt_config.auth_header_types:
        return auth["credential"]
```

### API Key Authentication

`django_matt/auth/api_keys/utils.py` — `get_api_key_from_request()`:

```python
parsed = _get_parsed_headers(request)
if parsed is not None:
    api_key = parsed.get("api_key")
    if api_key:
        return api_key
    auth = parsed.get("authorization")
    if auth and auth["type"] in ("Bearer", "ApiKey"):
        return auth["credential"].strip()
```

### Caching

Both consumers use `_get_parsed_headers()` which caches the result on `request._parsed_headers`. This means even if both JWT middleware and API key middleware are active, the headers are only parsed once.

## Performance

| Operation | Python | Rust | Speedup |
|-----------|--------|------|---------|
| Full header parse (5 headers) | ~1.0μs | ~0.8μs | **1.2x** |

The speedup is modest because Python string operations are already quite fast for short strings. The value is more in:

1. **One call instead of many** — amortizes FFI overhead
2. **Shared cache** — parse once, used by multiple middleware
3. **Structured output** — consumers don't need to re-split/re-parse

## Rust Implementation

Source: `rust/src/headers.rs`

- **parse_headers()** — reads from a Python dict (META), extracts known keys
- Authorization split uses `split_once(' ')` — only splits on the first space
- Accept parsing splits on `,`, then on `;q=` to extract quality values
- Content-Type splits on `;` to separate media type from parameters
- Malformed Authorization headers (no space) are skipped entirely
- Values are trimmed of whitespace

## Fallback

When Rust is unavailable, both `get_token_from_request()` and `get_api_key_from_request()` fall back to their original Python implementations — direct `request.headers.get()` and `request.META.get()` calls.

## Future Enhancements

- **Additional headers** — parse `X-Forwarded-For`, `X-Real-IP` for client IP extraction
- **Accept-Language** — quality-value parsing for i18n
- **Cache-Control** — parse directives for response caching decisions
- **CORS headers** — parse `Origin`, `Access-Control-Request-Method` for CORS middleware
