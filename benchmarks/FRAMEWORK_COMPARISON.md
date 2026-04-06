# Framework Comparison Benchmarks

Self-contained benchmarks measuring django-matt performance on key operations, compared against published DRF and Django Ninja baselines.

## What's measured

### Route resolution
- Static path: `/users/`
- Parameterized: `/users/{id}/`
- Nested params: `/orgs/{org_id}/teams/{team_id}/members/`
- Miss (404): `/nonexistent/path/`

### Schema serialization
- Small schema (5 fields) — validate + dump
- Medium schema (15 fields) — validate
- Large schema (50 fields) — validate
- Nested schema (3 levels deep) — validate
- List of 100 objects — model_dump()
- model_construct() — skip-validation fast path

### Request parsing
- JSON body parsing via orjson (small, medium, large payloads)
- JSON parse + Pydantic validation combined
- Query string parsing (Django QueryDict)
- Header extraction

### Full request lifecycle
- GET list: pagination + serialize 20 items + JSON encode
- GET detail: serialize single object + JSON encode
- POST create: JSON decode + validate + serialize + JSON encode

## Methodology

- Each operation runs 10,000 iterations (configurable via `-n`)
- 10 warmup iterations before measurement
- GC disabled during measurement
- Reports: mean, p95, p99, ops/sec
- Comparison columns show ratio vs published DRF/Ninja numbers

## Usage

```bash
make bench-compare
uv run python benchmarks/framework_comparison.py
uv run python benchmarks/framework_comparison.py -n 20000
uv run python benchmarks/framework_comparison.py --plain
```

## Baseline sources

DRF and Django Ninja numbers are hardcoded approximations from published benchmarks. They serve as directional reference points — absolute numbers vary by hardware. The ratios are what matter.
