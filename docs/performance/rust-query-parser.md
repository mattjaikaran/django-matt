# Query String Parser

## What It Is

A Rust-compiled parser that extracts structured parameters from URL query strings in a single pass. Called on every list endpoint to handle filtering, sorting, field selection, and pagination.

## Why It Exists

Django's `request.GET` is a `QueryDict` — it parses the raw query string into flat key-value pairs but doesn't understand the semantic structure of API query parameters. django-matt's views need to extract:

- `?fields=id,name,email` → field selection list
- `?filter[status]=active&filter[role]=admin` → filter dict
- `?sort=-created,name` → sort tuples with direction
- `?page=2&limit=20` → pagination parameters
- Everything else → extra parameters for Django-style filtering

In Python, this requires multiple passes: `request.GET.get("fields")` + split + strip, then iterate all keys for `filter[...]` patterns, then parse sort direction, etc. The Rust parser does all of this in one pass over the raw query string, including URL percent-decoding.

## How It Works

```python
from django_matt._accel import parse_query_string_rust

result = parse_query_string_rust(
    "fields=id,name,email&filter[status]=active&sort=-created,name&page=2&limit=20"
)

# result = {
#     "fields": ["id", "name", "email"],
#     "filters": {"status": "active"},
#     "sort": [("created", False), ("name", True)],  # (field, ascending)
#     "pagination": {"page": "2", "limit": "20"},
#     "extras": {},
# }
```

### Parsing rules:

| Pattern | Category | Example |
|---------|----------|---------|
| `fields=a,b,c` | Field selection | `fields=id,name` → `["id", "name"]` |
| `sort=-field,field` | Sort with direction | `sort=-created` → `[("created", False)]` |
| `ordering=-field` | Sort (alias) | Same as `sort` |
| `page`, `page_size`, `limit`, `offset`, `cursor`, `no_page` | Pagination | `page=2` → `{"page": "2"}` |
| `filter[key]=value` | Bracket filters | `filter[status]=active` → `{"status": "active"}` |
| Everything else | Extras (Django-style) | `status=active` → `{"status": "active"}` |

URL percent-decoding is included: `test%20query` → `test query`, `+` → space.

## Where It's Used

`django_matt/views/base.py` — the `_get_parsed_qs()` method:

```python
def _get_parsed_qs(self, request):
    cached = getattr(request, "_parsed_qs", None)
    if cached is not None:
        return cached
    if not HAS_RUST or parse_query_string_rust is None:
        return None
    qs = request.META.get("QUERY_STRING", "")
    parsed = parse_query_string_rust(qs)
    request._parsed_qs = parsed  # cached on request
    return parsed
```

The parsed result is cached on the request object so multiple consumers (field selection, ordering, filtering) share one parse.

Consumers in `ListView`:
- `_parse_field_selection()` — reads `parsed["fields"]`
- `_apply_ordering()` — reads `parsed["sort"]`
- `_apply_filters()` — falls back to `request.GET` for Django-style filters

## Performance

| Query Complexity | Python | Rust | Speedup |
|-----------------|--------|------|---------|
| Simple (`fields=id,name`) | ~1.2μs | ~0.5μs | **2.7x** |
| Filters (`filter[status]=active&filter[role]=admin`) | ~1.8μs | ~0.5μs | **3.8x** |
| Full (fields + filters + sort + pagination) | ~3.4μs | ~0.8μs | **4.0x** |
| Complex (many params + percent-encoding) | ~4.5μs | ~1.0μs | **4.6x** |

Speedup scales with query complexity because Python pays per-operation overhead (string splits, dict lookups) while Rust iterates bytes in a single pass.

## Rust Implementation

Source: `rust/src/querystring.rs`

- **parse_query_string()** — single-pass parser, dispatches each `key=value` pair to the appropriate category
- **url_decode()** — percent-decoding with `+` → space, handles malformed `%XX` gracefully (passes through)
- **from_hex()** — hex digit to nibble conversion
- Returns a Python dict with 5 sub-collections: fields (list), filters (dict), sort (list of tuples), pagination (dict), extras (dict)
- **3 Rust unit tests** for URL decoding edge cases

## Fallback

When Rust is unavailable, views fall back to `request.GET` access — the standard Django QueryDict. Field selection, ordering, and filtering all have Python fallback paths that read from `request.GET` directly.

## Future Enhancements

- **Typed pagination values** — parse `page` and `limit` as integers in Rust instead of returning strings
- **Filter operator parsing** — detect `__in`, `__gte`, `__lt` suffixes and split them out
- **Validation** — reject unknown filter keys early (before hitting Django ORM)
- **Streaming parse** — for very long query strings (> 4KB), avoid full string allocation by parsing in chunks
