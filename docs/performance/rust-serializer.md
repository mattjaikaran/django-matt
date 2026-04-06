# JSON Serializer with camelCase

## What It Is

A Rust-compiled JSON serializer that converts Python dicts to JSON bytes with optional snake_case → camelCase field renaming in a single pass. Used for list API responses when `CAMEL_CASE_API = True`.

## Why It Exists

When a Django API serves camelCase responses (common for JavaScript frontends), the serialization pipeline looks like:

```
ORM instance → Pydantic model_construct() → model_dump(by_alias=True) → orjson.dumps()
                                             ↑ alias generator runs     ↑ second pass
```

This is two passes: Pydantic walks every field to apply alias generators, then orjson walks the resulting dict to produce JSON. The Rust serializer combines both steps:

```
ORM instance → Pydantic model_construct() → model_dump() → serialize_dicts_to_json(dicts, alias_map)
                                             ↑ no aliases   ↑ single pass: rename + JSON
```

For plain JSON (no camelCase), orjson wins — it has deeper CPython integration (direct `PyObject` access, custom dtypes). The Rust serializer's value is specifically the combined rename+serialize path.

## How It Works

### List serialization (hot path for ListView)

```python
from django_matt._accel import serialize_dicts_to_json, build_camel_case_map

# Build alias map once (at view registration time)
alias_map = build_camel_case_map(["first_name", "last_name", "is_active", "id"])
# → {"first_name": "firstName", "last_name": "lastName", "is_active": "isActive"}
# Note: "id" has no underscore, so it's omitted (no rename needed)

# Serialize 10 user dicts with camelCase in one pass
dicts = [{"id": 1, "first_name": "Alice", "last_name": "Smith", "is_active": True}]
json_bytes = serialize_dicts_to_json(dicts, alias_map)
# → b'[{"id":1,"firstName":"Alice","lastName":"Smith","isActive":true}]'
```

### Single dict serialization

```python
from django_matt._accel import serialize_dict_to_json

json_bytes = serialize_dict_to_json(
    {"first_name": "Alice", "is_active": True},
    alias_map,
)
# → b'{"firstName":"Alice","isActive":true}'
```

### Supported Python types

| Python Type | JSON Output |
|------------|-------------|
| `str` | `"string"` (with escape handling for `"`, `\`, `\n`, `\r`, `\t`, control chars) |
| `int` | `123` |
| `float` | `1.5` (uses `ryu` crate for fast formatting; `NaN`/`Inf` → `null`) |
| `bool` | `true` / `false` |
| `None` | `null` |
| `list` | `[...]` (recursive) |
| `dict` | `{...}` (recursive, aliases applied to nested dicts too) |
| Other | `str(value)` as JSON string (fallback for UUID, datetime, etc.) |

## Where It's Used

`django_matt/views/base.py` — activated when `CAMEL_CASE_API = True` in Django settings:

```python
# In BoundView.__call__():
if isinstance(result, dict) and "items" in result:
    json_bytes = self.view.serialize_list_to_json_bytes(result["items"])
    if json_bytes is not None:
        # Build envelope with orjson, splice in Rust-serialized items
        envelope = {k: v for k, v in result.items() if k != "items"}
        body = orjson.dumps(envelope)[:-1] + b',"items":' + json_bytes + b"}"
        return HttpResponse(body, content_type="application/json")
```

The pattern is:
1. `serialize_list_to_json_bytes()` checks if Rust + camelCase are both active
2. If so, builds an alias map from the response schema's field names
3. Serializes the items list with rename in one pass
4. The envelope (count, total, page, etc.) is serialized with orjson
5. The two are spliced together as raw bytes

## Performance

| Operation | stdlib json | orjson | Rust | Rust + camelCase |
|-----------|------------|--------|------|------------------|
| 10 dicts | ~9.6μs | ~2.5μs | ~4.9μs | ~5.5μs |
| 100 dicts | ~96μs | ~22μs | ~48μs | ~53μs |

- **vs stdlib json**: 1.7-1.9x faster
- **vs orjson (plain)**: orjson is faster (deeper CPython integration)
- **vs orjson + Pydantic alias**: Rust is faster because it avoids the Pydantic alias pass

The Rust serializer is not a replacement for orjson — it's specifically for the camelCase rename path where the combined operation wins.

## Enabling camelCase

```python
# settings.py
DJANGO_MATT = {
    "CAMEL_CASE_API": True,
}
```

When enabled:
- Response schemas use `alias_generator=to_camel` + `by_alias=True`
- OpenAPI docs show camelCase field names
- List responses use Rust serializer when available

## Rust Implementation

Source: `rust/src/serializer.rs`

- **serialize_dicts_to_json()** — iterates a `PyList` of `PyDict`s, writes JSON to a pre-allocated `Vec<u8>` buffer
- **serialize_dict_to_json()** — single dict variant
- **write_dict()** — writes `{key:value,...}` with optional alias lookup per key
- **write_value()** — type dispatch: None, bool, int, float, str, list, dict, fallback
- **write_json_string()** — JSON escaping for strings (quotes, backslashes, control chars)
- **to_camel_case()** — snake_case → camelCase conversion (capitalize after underscores)
- **build_camel_case_map()** — builds a `PyDict` mapping snake names to camel names (only includes names with underscores)
- Uses `ryu` crate for fast float-to-string formatting
- Pre-allocates buffer at ~200 bytes per dict estimate

## Fallback

When Rust is unavailable or `CAMEL_CASE_API = False`:
- `serialize_list_to_json_bytes()` returns `None`
- `BoundView.__call__()` falls back to `JsonResponse(result, safe=False)`
- Pydantic's `model_dump(by_alias=True)` handles the camelCase rename
- Django's JSON encoder handles serialization

## Future Enhancements

- **DateTime/UUID native support** — handle these types directly instead of falling back to `str()`
- **Decimal support** — serialize `Decimal` as JSON number (currently falls back to string)
- **Streaming serialization** — for very large lists (1000+ items), write directly to the HTTP response instead of buffering
- **orjson integration** — use orjson for the non-camelCase path but Rust for the rename, avoiding the splice approach
