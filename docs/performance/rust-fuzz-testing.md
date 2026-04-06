# Fuzz Testing

## What It Is

Automated testing that feeds random, malformed, and adversarial inputs to Rust extension functions to find crashes, panics, and undefined behavior. Uses [cargo-fuzz](https://github.com/rust-fuzz/cargo-fuzz) (libFuzzer) with coverage-guided mutation.

## Why It Matters

Rust extensions process untrusted input from HTTP requests — URL paths, query strings, headers, JWT tokens. A panic in Rust crosses the FFI boundary and crashes the Python process. Unlike Python exceptions (which are caught and returned as 500s), a Rust panic terminates the entire ASGI worker.

Fuzz testing is especially important for:

- **URL percent-decoding** — malformed `%XX` sequences (truncated, non-hex chars)
- **JWT tokens** — arbitrary base64, missing parts, huge payloads
- **Header parsing** — unusual separators, empty values, very long strings
- **Unicode edge cases** — multi-byte UTF-8 in field names, query values, paths

## What We Test

Five fuzz targets, each exercising the core algorithms without PyO3:

| Target | What It Tests | Key Risks |
|--------|--------------|-----------|
| `fuzz_router` | Pattern parsing + radix tree insert/match | Stack overflow on deep nesting, panic on malformed `{param}` syntax |
| `fuzz_jwt` | Base64url roundtrip, HMAC signing, JWT encode/verify | Panic on malformed base64, signature comparison on empty data |
| `fuzz_querystring` | URL decoding, query string categorization | Truncated `%XX`, empty keys/values, very long inputs |
| `fuzz_serializer` | JSON string escaping, camelCase conversion | Control characters, multi-byte UTF-8, empty strings |
| `fuzz_headers` | Authorization/Accept/Content-Type parsing | Missing separators, empty values, weird quality values |

### Why standalone targets (not PyO3)

The Rust crate is a `cdylib` (Python extension) which can't be linked as a library dependency. Fuzz targets duplicate the pure Rust logic (parsing, encoding, matching) without the PyO3 bindings. This is the standard approach for fuzzing PyO3 crates — the PyO3 layer is thin (type conversion) while the logic layer is where bugs live.

## How It Works

cargo-fuzz uses LLVM's libFuzzer, a coverage-guided fuzzer:

1. **Start with an empty corpus** (or seed inputs)
2. **Mutate inputs** — bit flips, byte insertions, dictionary-based mutations
3. **Run the target** — if a new code path is covered, save the input to the corpus
4. **Repeat** — the corpus grows to cover more branches over time

If the target panics (assertion failure, unwrap on None, out-of-bounds), the crashing input is saved as an artifact for reproduction.

## Running

```bash
# Quick run (10s per target, all 5)
make rust-fuzz

# Long run on a specific target (5 minutes)
cd rust && cargo +nightly fuzz run fuzz_jwt -- -max_total_time=300

# Reproduce a crash
cd rust && cargo +nightly fuzz run fuzz_headers artifacts/fuzz_headers/crash-xxxx

# Minimize a crash input
cd rust && cargo +nightly fuzz tmin fuzz_headers artifacts/fuzz_headers/crash-xxxx
```

### Requirements

```bash
# One-time setup
cargo install cargo-fuzz
rustup toolchain install nightly
```

## What We Found

During initial fuzzing, one issue was discovered and fixed:

**Headers parser: malformed Authorization without space**

Input: `"BearerTokenWithoutSpace"` (no space between type and credential)

The Rust parser's `split_once(' ')` fallback was assuming any headerless token was a Bearer token, which contradicted the Python behavior of rejecting malformed headers. Fix: skip the authorization entry entirely when there's no space separator.

This was caught by the existing test suite after wiring the parser into auth middleware, but fuzz testing provides coverage for inputs that test suites don't anticipate.

## Corpus Management

Fuzz corpora are stored in `rust/fuzz/corpus/<target>/` and grow over time. They should be committed to the repo so that future fuzz runs start with full coverage:

```
rust/fuzz/
├── Cargo.toml
├── fuzz_targets/
│   ├── fuzz_router.rs
│   ├── fuzz_jwt.rs
│   ├── fuzz_querystring.rs
│   ├── fuzz_serializer.rs
│   └── fuzz_headers.rs
└── corpus/          # auto-generated, grows over time
    ├── fuzz_router/
    ├── fuzz_jwt/
    └── ...
```

## When to Fuzz

- **After adding a new Rust function** — create a fuzz target for it
- **After changing parsing logic** — run the relevant target for 5+ minutes
- **Before releases** — run all targets for 30+ minutes
- **In CI** — short runs (30s per target) on every PR that touches `rust/src/`

## Future Enhancements

### Structure-aware fuzzing

Current targets feed raw bytes. Using [arbitrary](https://crates.io/crates/arbitrary), targets could generate structured inputs:

```rust
#[derive(Arbitrary)]
struct FuzzRoute {
    method: String,
    segments: Vec<FuzzSegment>,
}

#[derive(Arbitrary)]
enum FuzzSegment {
    Static(String),
    Param(String),
    Wildcard(String),
}
```

This would reach deeper code paths faster by generating valid-shaped inputs.

### CI integration

A GitHub Actions job that runs fuzz targets on every PR:

```yaml
- name: Fuzz test
  run: |
    cd rust
    cargo +nightly fuzz run fuzz_router -- -max_total_time=30
    cargo +nightly fuzz run fuzz_jwt -- -max_total_time=30
    # ...
```

### OSS-Fuzz

For sustained fuzzing, the targets could be submitted to [OSS-Fuzz](https://github.com/google/oss-fuzz) for continuous coverage on Google's infrastructure.
