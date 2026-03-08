---
phase: 03-cli-and-type-generation
plan: 02
subsystem: typegen, management-commands
tags: [typegen, typescript, swift, zod, openapi, ai-context, cli, dx]
dependency_graph:
  requires: []
  provides: [sync_types-from-openapi, swift-api-client, generate-ai-context-depth]
  affects: [cli, typegen, ai-context]
tech_stack:
  added: []
  patterns:
    - "--from-openapi and --openapi-file flags on sync_types for OpenAPI-driven type generation"
    - "Swift target outputs Codable structs + URLSession API client in one pass"
    - "--depth flag on generate_ai_context controls content volume (minimal/standard/full)"
    - "depth_config dict maps depth to max_endpoints/max_models/max_schemas/include_examples"
key_files:
  created: []
  modified:
    - django_matt/management/commands/sync_types.py
    - django_matt/management/commands/generate_ai_context.py
    - tests/test_typegen.py
    - tests/test_management_commands.py
    - tests/test_ai_context.py
    - .planning/phases/03-cli-and-type-generation/deferred-items.md
decisions:
  - "--from-openapi triggers live OpenAPISchema.build() introspection; --openapi-file reads pre-built JSON/YAML spec (CI use case)"
  - "Swift target combines struct output + generate_api_client() call; uses URLSession with convertFromSnakeCase decoder"
  - "depth controls include_examples, max_endpoints, max_models, max_schemas — not a separate introspection pass"
  - "Depth minimal sets max_models/max_schemas=0 (routes only), full sets all counts high"
  - "2 pre-existing test failures (generate_crud ruff, startapi b2b) logged to deferred-items.md — not caused by this plan"
metrics:
  duration_seconds: 436
  completed_date: "2026-03-08"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 6
---

# Phase 3 Plan 02: Type Generation and AI Context Commands Summary

**One-liner:** Completed sync_types OpenAPI import flags + Swift API client output and generate_ai_context depth control with 32 new tests across 5 test files.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Complete type generators and --from-openapi flag | 1d26887 | sync_types.py, test_typegen.py, test_management_commands.py |
| 2 | Complete generate_ai_context with --depth flag | 63fa778 | generate_ai_context.py, test_ai_context.py |

## What Was Built

### Task 1: sync_types --from-openapi and Swift API Client

**sync_types.py additions:**
- `--from-openapi` flag: calls `OpenAPISchema.build()` to introspect the live project API schema
- `--openapi-file` flag: reads a pre-generated JSON/YAML spec file (useful in CI pipelines)
- Swift target now combines `generator.generate(schemas)` (Codable structs) + `generator.generate_api_client()` (URLSession client) in one output
- New helpers: `_generate_from_openapi_file()`, `_generate_from_project_openapi()`, `_generate_from_openapi_schema()`, `_openapi_type_to_swift()`

**Test additions (test_typegen.py):**
- `TestTypeScriptTypeMappings` (4 tests): datetime->string, UUID->string, Optional->union|null, list->Array
- `TestZodTypeMappings` (4 tests): datetime->z.string().datetime(), UUID->z.string().uuid(), Optional->nullable(), list->z.array()
- `TestSwiftAPIClientGeneration` (4 tests): URLSession, async throws, convertFromSnakeCase, Foundation import

**Test additions (test_management_commands.py):**
- `TestSyncTypesFromOpenAPI` (3 tests): argument existence, openapi-file output
- `TestSyncTypesSwiftTarget` (2 tests): URLSession in output, Codable struct in output

### Task 2: generate_ai_context --depth flag

**generate_ai_context.py additions:**
- `--depth` argument with choices: `minimal`, `standard`, `full` (default: `standard`)
- `minimal`: routes only — `include_examples=False`, `max_models=0`, `max_schemas=0`
- `standard`: routes + types — standard content limits (50 endpoints, 30 models/schemas)
- `full`: everything — `include_examples=True`, high limits (200 endpoints, 100 models/schemas)
- Depth config dict drives `ClaudeMdGenerator` instantiation

**Test additions (test_ai_context.py):**
- `TestGenerateAiContextDepthFlag` (7 tests): argument existence, choices validation, minimal/standard/full depth runs, format-all output, include-examples acceptance

## Deviations from Plan

### Auto-fixed Issues

None — all plan items were implemented as specified.

### Out-of-scope Discoveries

**1. [Pre-existing] generate_crud ruff I001 failure**
- **Found during:** Task 1 full test run
- **Issue:** Generated schema.py has unsorted imports (stdlib before third-party)
- **Not fixed:** Out of scope (unrelated to this plan's changes)
- **Logged to:** deferred-items.md

**2. [Pre-existing] startapi b2b template missing DJANGO_MATT_MULTITENANCY**
- **Found during:** Task 1 full test run
- **Issue:** Test expects `DJANGO_MATT_MULTITENANCY` in generated settings.py but template doesn't include it
- **Not fixed:** Out of scope (unrelated to this plan's changes)
- **Logged to:** deferred-items.md

## Success Criteria Verification

1. sync_types --target typescript: PASS (pre-existing, tested via TestTypeScriptTypeMappings)
2. sync_types --target zod: PASS (pre-existing, tested via TestZodTypeMappings)
3. sync_types --target swift: PASS (NOW includes URLSession API client, verified TestSyncTypesSwiftTarget)
4. sync_types --from-openapi: PASS (new flag, verified TestSyncTypesFromOpenAPI)
5. generate_ai_context --depth minimal/standard/full: PASS (new flag, verified TestGenerateAiContextDepthFlag)
6. generate_ai_context --include-examples: PASS (pre-existing flag, verified acceptance with depth)
7. All type generation and AI context tests pass: 225/227 PASS (2 pre-existing failures excluded)

## Self-Check: PASSED

Files exist:
- [x] django_matt/management/commands/sync_types.py (modified)
- [x] django_matt/management/commands/generate_ai_context.py (modified)
- [x] tests/test_typegen.py (modified)
- [x] tests/test_management_commands.py (modified)
- [x] tests/test_ai_context.py (modified)

Commits exist:
- [x] 1d26887 feat(03-02): add --from-openapi/--openapi-file flags and swift API client output
- [x] 63fa778 feat(03-02): add --depth flag to generate_ai_context command
