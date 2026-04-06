# Radix Tree URL Router

## What It Is

A Rust-compiled radix tree that replaces Django's regex-based URL resolver for route matching. This is the single hottest path in any web framework — it runs on every incoming request.

## Why It Exists

Django's URL resolver compiles URL patterns to regular expressions and matches them sequentially. For 20 routes, a miss (404) requires checking all 20 regexes. A match on the last route also checks all 20. This is O(n) in route count.

A radix tree (also called a prefix tree or trie) matches in O(path_length) — independent of how many routes are registered. The tree structure shares common prefixes, so `/users`, `/users/{id}`, and `/users/{id}/posts` share the `/users` prefix node.

## How It Works

```
Root
├── users/
│   ├── [endpoint: GET → list_users, POST → create_user]
│   ├── me [endpoint: GET → current_user]
│   └── {id}/ [param child]
│       ├── [endpoint: GET → user_detail, PUT → update_user]
│       └── posts/
│           └── {post_id} [endpoint: GET → user_post_detail]
├── products/
│   └── ...
└── health [endpoint: GET → health_check]
```

### Key properties:

- **Static children first** — `/users/me` always matches before `/users/{id}`, regardless of registration order
- **Method isolation** — GET and POST on `/users` are stored as separate endpoints on the same node
- **Wildcard support** — `{path:*}` catches remaining path segments (e.g., `/files/{path:*}` matches `/files/a/b/c.txt`)
- **Trailing slash normalization** — `/users/` and `/users` match the same route

## Where It's Used

`django_matt/core/router.py` — the `radix_dispatch()` function:

```python
from django_matt._accel import HAS_RUST, RadixRouter

if HAS_RUST:
    router = RadixRouter()
    for method, pattern, endpoint_id in routes:
        router.add_route(method, pattern, endpoint_id)

    result = router.match_route("GET", "/users/42")
    # → ("user_detail", {"id": "42"})
```

Routes are registered automatically when `get_urls()` is called. The radix tree is built once and reused for all requests.

## Performance

| Scenario | Python Regex | Rust Radix | Speedup |
|----------|-------------|------------|---------|
| First route hit | ~1.7μs | ~1.0μs | 1.7x |
| Mid-route hit | ~4.0μs | ~1.5μs | 2.7x |
| Last route hit | ~6.6μs | ~1.7μs | 3.9x |
| 404 (miss) | ~8.5μs | ~0.7μs | **12.7x** |
| **Average (8 cases)** | **~6.6μs** | **~1.7μs** | **4.0x** |

The biggest wins are on misses and late matches — exactly the cases where Django's linear scan is most expensive.

## Rust Implementation

Source: `rust/src/router.rs`

- **Node struct** — prefix string, static children, optional param child, optional wildcard child, endpoints by method
- **parse_pattern()** — splits URL patterns into `Static`, `Param`, and `Wildcard` segments
- **insert_route()** — recursive insertion, sharing prefix nodes
- **match_segments()** — recursive matching with backtracking (static → param → wildcard priority)
- **12 Rust unit tests** covering static, param, wildcard, method isolation, root path, nested params, priority

## Fallback

When Rust is not installed, the router falls back to Django's built-in URL resolver. No code changes needed — the `_accel.py` import guard handles it transparently.

## Future Enhancements

- **Route compression** — merge single-child static nodes to reduce tree depth
- **Compiled route table** — pre-compute a flat array for small route sets (< 10 routes) where the tree overhead isn't worth it
- **Route conflict detection** — warn at startup when two routes would match the same path
