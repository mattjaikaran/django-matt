# Migration Acceleration

> Solve the 2-hour migration problem for large Django codebases.

## Table of Contents

- [The Problem](#the-problem)
- [Solution Overview](#solution-overview)
- [Quick Start](#quick-start)
- [SQL Baselines](#sql-baselines)
- [Parallel Migration Execution](#parallel-migration-execution)
- [Migration Profiling](#migration-profiling)
- [Smart Squashing](#smart-squashing)
- [Safety Analysis](#safety-analysis)
- [Database-Specific Considerations](#database-specific-considerations)
- [CI/CD Integration](#cicd-integration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)
- [Performance Benchmarks](#performance-benchmarks)

---

## The Problem

When Django projects grow, migrations become a critical bottleneck that impacts every part of your development workflow.

### Why Migrations Slow Down

**1. Linear Execution**

Django runs migrations sequentially, one after another. With 500 migrations, even if each takes 0.5 seconds, you're looking at over 4 minutes. But migrations rarely take 0.5 seconds—data migrations, index builds, and schema changes can take minutes each.

```
Migration 1 (0.2s) → Migration 2 (0.3s) → ... → Migration 500 (1.5s)
Total: Sum of all individual times
```

**2. Dependency Loading**

Before running a single migration, Django must:
- Load all migration files from disk
- Build a complete dependency graph
- Resolve conflicts and ordering
- Check which migrations are already applied

With hundreds of migrations across dozens of apps, this overhead compounds.

**3. Data Migrations**

`RunPython` operations that touch data are the worst offenders:

```python
# This innocent-looking migration can take hours on large tables
def backfill_user_emails(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():  # Iterating millions of rows
        user.email_normalized = user.email.lower()
        user.save()
```

**4. Index Creation**

Creating indexes on large tables locks the table and can take significant time:

```python
migrations.AddIndex(
    model_name='order',
    index=models.Index(fields=['created_at', 'status']),
)
# On a table with 10M rows, this could take 5-30 minutes
```

**5. Cumulative Technical Debt**

Over years of development:
- Migrations accumulate (50-100+ per app is common)
- Old migrations reference deleted models
- Circular dependencies emerge
- RunPython/RunSQL can't be optimized

### The Impact

| Scenario | Without Optimization | With django-matt |
|----------|---------------------|------------------|
| New developer setup | 2+ hours | 30 seconds |
| CI/CD pipeline | 45 minutes | 3 minutes |
| Staging deployment | 30 minutes | 2 minutes |
| Local test runs | 5 minutes | 30 seconds |

---

## Solution Overview

django-matt provides four complementary strategies:

### 1. SQL Baselines
Skip running migrations entirely. Load a SQL dump of the schema at a known state, then only run migrations created after that point.

**Best for**: New developer setup, CI/CD pipelines, fresh environments

### 2. Parallel Execution
Analyze the migration dependency graph and run independent migrations concurrently in "waves."

**Best for**: Applying multiple pending migrations, speeding up deployments

### 3. Migration Profiling
Understand exactly which migrations are slow and why before running them. Track historical timing to identify patterns.

**Best for**: Pre-deployment analysis, identifying optimization targets

### 4. Smart Squashing
Consolidate old, applied migrations into fewer files without changing the schema.

**Best for**: Reducing file count, speeding up dependency resolution

---

## Quick Start

### Diagnose Your Current State

```bash
# Get an overview of your migration landscape
python manage.py matt_migrate --stats

# See which pending migrations will be slow
python manage.py matt_migrate --profile

# Check for unsafe patterns
python manage.py matt_migrate --check
```

### Speed Up New Environment Setup

```bash
# On your production/main database, create a baseline
python manage.py matt_baseline create v1.0.0 --notes "Initial baseline"

# Commit the baseline to your repo
git add migration_baselines/
git commit -m "Add migration baseline v1.0.0"

# On any new database (dev, CI, staging):
python manage.py matt_baseline load v1.0.0
python manage.py migrate  # Only runs new migrations
```

### Speed Up Pending Migrations

```bash
# Preview how migrations would be parallelized
python manage.py matt_migrate --plan-waves

# Run migrations in parallel (with confirmation)
python manage.py matt_migrate --parallel
```

### Reduce Migration File Count

```bash
# Find apps with many migrations
python manage.py matt_squash --analyze

# Squash with preview
python manage.py matt_squash accounts 0001 0100 --preview

# Execute squash
python manage.py matt_squash accounts 0001 0100
```

---

## SQL Baselines

SQL baselines are the most powerful optimization for environment setup. Instead of replaying hundreds of migrations, you load a SQL dump that represents the schema at a specific point in time.

### How It Works

```
Traditional Approach:
┌──────────┐    ┌──────────┐    ┌──────────┐         ┌──────────┐
│Migration │ -> │Migration │ -> │Migration │ -> ... ->│Migration │
│   0001   │    │   0002   │    │   0003   │         │   0500   │
└──────────┘    └──────────┘    └──────────┘         └──────────┘
                          Time: 2+ hours

Baseline Approach:
┌────────────────────────────────────────────┐    ┌──────────┐
│     SQL Baseline (schema at migration 500) │ -> │Migration │
│                  ~5 seconds                │    │   0501   │
└────────────────────────────────────────────┘    └──────────┘
                          Time: ~30 seconds
```

### Creating a Baseline

```bash
# Basic creation
python manage.py matt_baseline create v1.0.0

# With notes (recommended)
python manage.py matt_baseline create v1.0.0 --notes "Release 1.0 - Production schema"

# Without compression (for debugging)
python manage.py matt_baseline create v1.0.0 --no-compress
```

#### What Gets Created

```
migration_baselines/
└── v1.0.0/
    ├── schema.sql.gz      # Compressed schema dump
    └── manifest.json      # Metadata
```

**manifest.json structure:**

```json
{
  "version": "v1.0.0",
  "created_at": "2024-01-15T12:00:00Z",
  "schema_hash": "abc123def456",
  "applied_migrations": {
    "accounts": ["0001_initial", "0002_add_email", "..."],
    "products": ["0001_initial", "0002_add_sku", "..."],
    "orders": ["0001_initial", "..."]
  },
  "db_vendor": "postgresql",
  "django_version": "5.2",
  "notes": "Release 1.0 - Production schema"
}
```

### Loading a Baseline

```bash
# Load the baseline
python manage.py matt_baseline load v1.0.0

# Then run any migrations created after the baseline
python manage.py migrate
```

#### What Happens During Load

1. **Schema Creation**: The SQL dump is executed, creating all tables, indexes, constraints
2. **Migration Faking**: All migrations recorded in the manifest are marked as "applied" in `django_migrations` table
3. **Verification**: The system reports how many migrations were faked and how many remain

```
Loading baseline 'v1.0.0'...

Baseline 'v1.0.0' loaded successfully!
  Migrations faked: 523
  Migrations remaining: 5
  Elapsed: 4.32s

Run 'python manage.py migrate' to apply the remaining 5 migrations.
```

### Managing Baselines

#### List All Baselines

```bash
python manage.py matt_baseline list
```

Output:
```
Available baselines:

  v1.2.0
    Created: 2024-03-15T10:30:00Z
    DB: postgresql
    Django: 5.2
    Migrations: 587 across 12 apps
    Hash: abc123def456

  v1.1.0
    Created: 2024-02-01T08:00:00Z
    DB: postgresql
    Django: 5.2
    Migrations: 545 across 12 apps
    Hash: 789xyz123abc

  v1.0.0
    Created: 2024-01-15T12:00:00Z
    DB: postgresql
    Django: 5.2
    Migrations: 523 across 11 apps
    Hash: def456ghi789
    Notes: Release 1.0 - Production schema
```

#### Get Detailed Info

```bash
python manage.py matt_baseline info v1.0.0
```

Output:
```
Baseline: v1.0.0
Created: 2024-01-15T12:00:00Z
Database: postgresql
Django version: 5.2
Schema hash: def456ghi789
Notes: Release 1.0 - Production schema

Migrations by app:
  accounts: 85 migrations
    - 0001_initial
    - 0002_add_email
    ... 81 more ...
    - 0084_add_mfa
    - 0085_update_profile
  products: 64 migrations
    - 0001_initial
    - 0002_add_sku
    ... 60 more ...
    - 0063_add_variants
    - 0064_update_pricing
  orders: 52 migrations
    ...

Total: 523 migrations across 11 apps
```

#### Verify Integrity

```bash
python manage.py matt_baseline verify v1.0.0
```

Checks that the schema dump hasn't been modified since creation.

#### Delete Old Baselines

```bash
# With confirmation
python manage.py matt_baseline delete v0.9.0

# Skip confirmation
python manage.py matt_baseline delete v0.9.0 --force
```

### Baseline Versioning Strategy

#### Semantic Versioning (Recommended)

Align baselines with your release versions:

```bash
python manage.py matt_baseline create v1.0.0
python manage.py matt_baseline create v1.1.0
python manage.py matt_baseline create v2.0.0
```

#### Date-Based Versioning

For projects without formal releases:

```bash
python manage.py matt_baseline create 2024-01
python manage.py matt_baseline create 2024-02
python manage.py matt_baseline create 2024-03
```

#### Auto-Generated Version

If you don't provide a version, one is suggested based on git tags or current date:

```bash
python manage.py matt_baseline create
# Using auto-generated version: v1.0
```

### When to Create Baselines

| Event | Action |
|-------|--------|
| Major release | Create baseline (e.g., v2.0.0) |
| After squashing migrations | Create new baseline |
| Quarterly (for active projects) | Create baseline |
| Before large data migration | Create baseline as safety net |

---

## Parallel Migration Execution

Django runs migrations one at a time, but many migrations have no dependencies on each other. Parallel execution identifies these independent migrations and runs them concurrently.

### How It Works

The system analyzes the migration dependency graph and groups migrations into "waves":

```
Traditional Sequential:
┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
│ M1  │->│ M2  │->│ M3  │->│ M4  │->│ M5  │->│ M6  │
└─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘
Time: 6 units (sum of all)

Parallel Waves:
Wave 1:           Wave 2:           Wave 3:
┌─────┐ ┌─────┐   ┌─────┐ ┌─────┐   ┌─────┐
│ M1  │ │ M2  │   │ M3  │ │ M4  │   │ M6  │
└─────┘ └─────┘   └─────┘ └─────┘   └─────┘
        ┌─────┐
        │ M5  │
        └─────┘
Time: 3 units (max of each wave)
```

### Preview the Execution Plan

```bash
python manage.py matt_migrate --plan-waves
```

Output:
```
Parallel Execution Plan
==================================================
Migrations will execute in 4 waves.
Migrations in the same wave run concurrently.

Wave 1 (6 migrations):
  - accounts.0086_add_phone
  - products.0065_add_category
  - orders.0053_add_tracking
  - payments.0034_add_refunds
  - notifications.0022_add_push
  - analytics.0015_add_events

Wave 2 (3 migrations):
  - accounts.0087_phone_validation
  - products.0066_category_tree
  - orders.0054_tracking_history

Wave 3 (2 migrations):
  - accounts.0088_mfa_setup
  - products.0067_variant_pricing

Wave 4 (1 migration):
  - orders.0055_final_status

Total: 12 migrations across 4 waves
```

### Execute in Parallel

```bash
python manage.py matt_migrate --parallel
```

Output:
```
Executing migrations in parallel waves...
Note: Parallel migration is experimental. Ensure your database supports concurrent DDL.

Wave 1: executing 6 migrations in parallel
  [OK] accounts.0086_add_phone (0.45s)
  [OK] products.0065_add_category (0.62s)
  [OK] orders.0053_add_tracking (0.38s)
  [OK] payments.0034_add_refunds (0.55s)
  [OK] notifications.0022_add_push (0.29s)
  [OK] analytics.0015_add_events (0.41s)
  Wave time: 0.68s (sequential would be: 2.70s)

Wave 2: executing 3 migrations in parallel
  [OK] accounts.0087_phone_validation (1.23s)
  [OK] products.0066_category_tree (0.89s)
  [OK] orders.0054_tracking_history (0.95s)
  Wave time: 1.28s (sequential would be: 3.07s)

Wave 3: executing 2 migrations in parallel
  [OK] accounts.0088_mfa_setup (0.67s)
  [OK] products.0067_variant_pricing (0.72s)
  Wave time: 0.76s (sequential would be: 1.39s)

Wave 4: executing 1 migration
  [OK] orders.0055_final_status (0.34s)
  Wave time: 0.38s (sequential would be: 0.34s)

Summary:
  Migrations applied: 12
  Migrations failed: 0
  Total time: 3.42s
  Sequential would take: 7.50s
  Speedup: 2.2x

All migrations applied successfully!
```

### Dry Run

Preview without executing:

```bash
python manage.py matt_migrate --parallel --dry-run
```

### Configuring Workers

```bash
# Default is 4 workers
python manage.py matt_migrate --parallel --workers 8
```

### When Parallel Execution Helps Most

| Scenario | Typical Speedup |
|----------|-----------------|
| Many small schema changes | 3-8x |
| Multiple independent apps | 2-5x |
| Index-heavy migrations | 2-4x |
| Data migrations | 1-2x (often sequential) |

### When to Avoid Parallel Execution

- **Data migrations touching shared tables**: These often have implicit dependencies
- **Migrations with RunSQL**: May have undeclared dependencies
- **First-time production deploy**: Use sequential for safety, then parallelize future runs
- **SQLite**: Doesn't support concurrent writes well

---

## Migration Profiling

Before running migrations, understand what you're dealing with. Profiling helps identify bottlenecks and plan accordingly.

### Project Statistics

```bash
python manage.py matt_migrate --stats
```

Output:
```
Migration Statistics
========================================
Total migrations: 587
Applied: 575
Pending: 12

Total operations: 2,456
Data migrations: 67
Index operations: 134

Estimated pending time: 45.2s

Pending complexity breakdown:
  trivial: 5
  simple: 4
  moderate: 2
  complex: 1

Migrations per app:
  accounts: 89
  products: 76
  orders: 65
  payments: 52
  notifications: 45
  analytics: 38
  ...

Tip: Run --profile to see which pending migrations are slowest.
```

### Profile Pending Migrations

```bash
python manage.py matt_migrate --profile
```

Output:
```
Top 10 slowest pending migrations:
==================================================

accounts.0088_backfill_normalized_emails [extreme] ~25.0s
  Operations: 1
  ⚠ Contains data migration
  ⚠ RunPython operation may be slow and blocks parallel execution

products.0067_add_search_index [complex] ~8.0s
  Operations: 2
  ⚠ Creates indexes
  ⚠ Index creation on large table may lock for extended period

orders.0055_add_composite_index [moderate] ~3.0s
  Operations: 1
  ⚠ Creates indexes

accounts.0089_add_verification_field [simple] ~1.5s
  Operations: 1
  ⚠ Adding non-nullable field to accounts may lock table

payments.0035_refund_status [simple] ~0.8s
  Operations: 2

...

Total estimated time: 45.2s (0.8 minutes)

Parallel potential: 4 waves, ~18.5s, 2.4x speedup
Run with --parallel to execute in parallel waves.
```

### Complexity Classifications

| Level | Criteria | Typical Time |
|-------|----------|--------------|
| **trivial** | 0-2 operations, no data migrations | < 1s |
| **simple** | 3-5 operations, no data migrations | 1-5s |
| **moderate** | 6-10 operations or simple indexes | 5-30s |
| **complex** | Data migrations, multiple indexes | 30s-5min |
| **extreme** | Large table data migrations | 5min+ |

### Historical Timing

The profiler records actual migration times for future reference:

```bash
# Show the 10 slowest migrations from history
python manage.py matt_migrate --slowest 10
```

Output:
```
Top 10 slowest migrations (from history):
==================================================
  1. accounts.0045_backfill_legacy_users: 342.5s average
  2. products.0032_create_search_index: 187.2s average
  3. orders.0028_add_audit_fields: 95.8s average
  4. accounts.0067_normalize_phone_numbers: 78.3s average
  5. payments.0019_encrypt_card_data: 65.1s average
  ...
```

### Filter by App

```bash
# Profile only specific app
python manage.py matt_migrate --profile --app accounts
```

---

## Smart Squashing

Over time, you accumulate hundreds of migrations. Squashing consolidates them into fewer files without changing the schema.

### Why Squash?

1. **Faster dependency resolution**: Django loads all migration files at startup
2. **Cleaner history**: Easier to understand schema evolution
3. **Reduced disk I/O**: Fewer files to read
4. **Simpler debugging**: Fewer places to look for issues

### Analyze Squash Opportunities

```bash
python manage.py matt_squash --analyze
```

Output:
```
Squash Analysis
==================================================

accounts: 89 applied migrations
  Range: 0001_initial → 0089_latest
  Suggested: python manage.py matt_squash accounts 0001 0089

products: 76 applied migrations
  Range: 0001_initial → 0076_latest
  Suggested: python manage.py matt_squash products 0001 0076

orders: 65 applied migrations
  Range: 0001_initial → 0065_latest
  Suggested: python manage.py matt_squash orders 0001 0065

3 app(s) could benefit from squashing.
```

### Adjust Minimum Threshold

```bash
# Only suggest apps with 20+ migrations
python manage.py matt_squash --analyze --min-migrations 20
```

### Preview a Squash

Before squashing, always preview:

```bash
python manage.py matt_squash accounts 0001 0089 --preview
```

Output:
```
Squash Preview: accounts
==================================================
Migrations to squash: 89
  0001_initial, 0002_add_email, 0003_add_profile, 0004_add_avatar,
  0005_add_settings, ...
  ... and 84 more

Operations: 456 → 52
Reduction: 404 operations (88.6%)

Warnings:
  ⚠ 0023_backfill_names: RunPython — cannot be fully optimized
  ⚠ 0045_migrate_legacy_users: RunPython — cannot be fully optimized
  ⚠ 0067_normalize_phones: RunSQL — will be preserved as-is
  ⚠ 0078_encrypt_ssn: RunSQL — will be preserved as-is
```

### Execute Squash

```bash
python manage.py matt_squash accounts 0001 0089
```

Interactive confirmation:
```
Squash Preview: accounts
==================================================
Migrations to squash: 89
Operations: 456 → 52
Reduction: 404 operations (88.6%)

Warnings:
  ⚠ 4 RunPython/RunSQL operations will be preserved

Proceed with squash? [y/N] y

Squashing...

Squash complete! Created: squashed_0001_0089

Next steps:
1. Review the generated migration file
2. Test with: python manage.py migrate --check
3. After deploying, delete the old migration files
4. Remove the replaces list from the squashed migration
```

### Squash All Apps

```bash
# Preview all
python manage.py matt_squash --all --preview

# Execute all
python manage.py matt_squash --all
```

### Post-Squash Cleanup

After squashing and deploying:

1. **Verify**: Run migrations on a fresh database
2. **Delete old files**: Remove the squashed migration files
3. **Update squash file**: Remove the `replaces` attribute
4. **Create new baseline**: `python manage.py matt_baseline create`

---

## Safety Analysis

Detect potentially dangerous migration patterns before they cause production incidents.

### Check for Issues

```bash
python manage.py matt_migrate --check
```

Output:
```
⚠ accounts/0090_add_required_field
  AddField: phone_verified (NOT NULL, no default)
  Adding non-nullable field without default will fail on existing rows

⚠ accounts/0091_rename_legacy_column
  RenameField: old_email → legacy_email
  Column rename may break running application code

✗ products/0078_create_fulltext_index
  AddIndex: products_search_idx
  Index creation on large table may lock for extended period
  Consider using CREATE INDEX CONCURRENTLY

⚠ orders/0066_add_foreign_key
  AddField: customer_id (ForeignKey)
  Adding foreign key to existing table requires data validation

4 issue(s) found.
Run with --rewrite to see safe alternatives.
```

### Get Safe Rewrites

```bash
python manage.py matt_migrate --rewrite
```

Output:
```
⚠ accounts/0090_add_required_field
  AddField: phone_verified (NOT NULL, no default)
  Adding non-nullable field without default will fail on existing rows

  Safe rewrite steps:
    Step 1: Add field as nullable
      ALTER TABLE accounts_user ADD COLUMN phone_verified BOOLEAN NULL;
    Step 2: Backfill default values
      UPDATE accounts_user SET phone_verified = false WHERE phone_verified IS NULL;
    Step 3: Add NOT NULL constraint
      ALTER TABLE accounts_user ALTER COLUMN phone_verified SET NOT NULL;

✗ products/0078_create_fulltext_index
  AddIndex: products_search_idx
  Index creation on large table may lock for extended period

  Safe rewrite steps:
    Step 1: Create index concurrently (PostgreSQL)
      CREATE INDEX CONCURRENTLY products_search_idx ON products_product (...);
    Step 2: Verify index is valid
      SELECT indexrelid::regclass, indisvalid FROM pg_index WHERE indexrelid = 'products_search_idx'::regclass;
```

### Visualize Dependencies

```bash
# ASCII graph
python manage.py matt_migrate --graph

# DOT format (for Graphviz)
python manage.py matt_migrate --graph --format dot > migrations.dot
dot -Tpng migrations.dot -o migrations.png

# Mermaid format (for documentation)
python manage.py matt_migrate --graph --format mermaid
```

### Check for Circular Dependencies

```bash
python manage.py matt_migrate --check-cycles
```

### Check for Branch Conflicts

```bash
python manage.py matt_migrate --check-conflicts
```

---

## Database-Specific Considerations

### PostgreSQL

PostgreSQL is the best choice for parallel migrations due to excellent concurrent DDL support.

**Baseline commands used:**
```bash
pg_dump --schema-only --no-owner --no-privileges --no-comments
psql --quiet --no-psqlrc
```

**Parallel execution**: Fully supported. PostgreSQL handles concurrent DDL well.

**Recommended settings:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
```

### MySQL

MySQL supports baselines but has limitations with parallel execution.

**Baseline commands used:**
```bash
mysqldump --no-data --skip-comments --compact
mysql
```

**Parallel execution**: Limited. MySQL's table-level locking can cause issues with concurrent DDL. Use with caution.

**Recommended approach**: Use baselines aggressively, limit parallel workers to 2.

### SQLite

SQLite is supported for development but has significant limitations.

**Baseline commands used:**
```bash
sqlite3 database.db ".schema"
```

**Parallel execution**: Not recommended. SQLite doesn't handle concurrent writes well.

**Recommended approach**: Use baselines only. Run migrations sequentially.

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Setup database with baseline
        run: |
          uv run python manage.py matt_baseline load v1.0.0
          uv run python manage.py migrate
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/postgres

      - name: Run tests
        run: uv run pytest
```

### GitLab CI

```yaml
test:
  image: python:3.12
  services:
    - postgres:15
  variables:
    POSTGRES_PASSWORD: postgres
    DATABASE_URL: postgres://postgres:postgres@postgres:5432/postgres
  script:
    - pip install uv
    - uv sync
    - uv run python manage.py matt_baseline load v1.0.0
    - uv run python manage.py migrate
    - uv run pytest
```

### Docker Compose for Local Development

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    build: .
    command: >
      sh -c "python manage.py matt_baseline load v1.0.0 &&
             python manage.py migrate &&
             python manage.py runserver 0.0.0.0:8000"
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - db
    environment:
      DATABASE_URL: postgres://postgres:postgres@db:5432/postgres

volumes:
  postgres_data:
```

### Makefile Integration

```makefile
.PHONY: db-setup db-baseline db-migrate db-reset

# Fresh setup from baseline
db-setup:
	python manage.py matt_baseline load v1.0.0
	python manage.py migrate

# Create new baseline
db-baseline:
	@read -p "Version (e.g., v1.1.0): " version; \
	python manage.py matt_baseline create $$version

# Run migrations with profiling
db-migrate:
	python manage.py matt_migrate --profile
	@read -p "Continue with parallel execution? [y/N] " confirm; \
	if [ "$$confirm" = "y" ]; then \
		python manage.py matt_migrate --parallel; \
	else \
		python manage.py migrate; \
	fi

# Reset database and reload baseline
db-reset:
	python manage.py flush --no-input
	python manage.py matt_baseline load v1.0.0
	python manage.py migrate
```

---

## Best Practices

### 1. Create Baselines at Release Boundaries

```bash
# As part of release process
git checkout main
python manage.py matt_baseline create v1.2.0 --notes "Release 1.2.0"
git add migration_baselines/
git commit -m "Add migration baseline v1.2.0"
git tag v1.2.0
```

### 2. Profile Before Deploying

```bash
# Before production deploy
python manage.py matt_migrate --profile

# If data migrations present
python manage.py matt_migrate --check

# Consider running slow migrations during maintenance window
```

### 3. Use Parallel Execution in Non-Production First

```bash
# Test in staging
python manage.py matt_migrate --parallel

# Once confident, use in production
```

### 4. Squash Periodically

```bash
# Every 3-6 months or at major releases
python manage.py matt_squash --analyze
python manage.py matt_squash accounts 0001 0100
python manage.py matt_baseline create v2.0.0
```

### 5. Monitor Migration Growth

Add to your monitoring/alerting:

```python
# In a management command or health check
from django_matt.migration_tools import MigrationProfiler

profiler = MigrationProfiler()
stats = profiler.get_project_stats()

if stats.total_migrations > 500:
    alert("Migration count exceeds 500, consider squashing")

if stats.pending_migrations > 20:
    alert(f"{stats.pending_migrations} pending migrations")
```

### 6. Document Your Strategy

Create a `MIGRATIONS.md` in your project:

```markdown
# Migration Strategy

## Baselines

We create baselines at each major release. Current baseline: v1.2.0

To set up a fresh database:
```bash
python manage.py matt_baseline load v1.2.0
python manage.py migrate
```

## Squashing

We squash migrations annually. Last squash: January 2024.

## Deployment

1. Profile migrations: `python manage.py matt_migrate --profile`
2. For >10 migrations, use parallel: `python manage.py matt_migrate --parallel`
3. For data migrations, schedule maintenance window
```

---

## Troubleshooting

### Baseline Load Fails with "Vendor Mismatch"

**Error**: `Baseline is for postgresql, current DB is mysql`

**Cause**: Baselines are database-specific.

**Solution**: Create separate baselines for each database vendor, or standardize on one database.

### Parallel Execution Causes Deadlock

**Error**: `deadlock detected` or migrations hang

**Cause**: Migrations have undeclared dependencies.

**Solution**:
1. Use sequential execution for the problematic migrations
2. Add explicit dependencies to migrations
3. Run with `--parallel --dry-run` to identify the conflicting migrations

### Squash Fails with "Circular Dependency"

**Error**: `Circular dependency detected`

**Cause**: Migration dependencies form a cycle.

**Solution**:
1. Run `python manage.py matt_migrate --check-cycles` to identify the cycle
2. Fix the dependencies before squashing
3. May need to manually edit migration files

### Baseline Schema Hash Mismatch

**Error**: `Hash mismatch: expected abc123, got def456`

**Cause**: The schema dump was modified after creation.

**Solution**:
1. Delete the corrupted baseline: `python manage.py matt_baseline delete v1.0.0`
2. Create a fresh baseline: `python manage.py matt_baseline create v1.0.0`

### Historical Timing Data Missing

**Issue**: `--slowest` shows no data

**Cause**: Timing data is stored locally and may not exist yet.

**Solution**: Migration times are recorded automatically when using django-matt. Run some migrations first, then check again.

### Profiler Overestimates Time

**Issue**: Estimated time is much higher than actual

**Cause**: Profiler uses conservative estimates, especially for data migrations.

**Solution**: Use `--slowest` with historical data for more accurate estimates. The profiler intentionally overestimates to prevent surprises.

---

## API Reference

### MigrationBaseline

```python
from django_matt.migration_tools import MigrationBaseline, BaselineInfo

# Initialize (uses Django's BASE_DIR by default)
baseline = MigrationBaseline()

# Or specify custom path
baseline = MigrationBaseline(base_path=Path("/custom/path"))

# Create a baseline
result = baseline.create(
    version="v1.0.0",
    notes="Release 1.0",
    compress=True  # gzip the dump
)
# result.success: bool
# result.version: str
# result.dump_path: Path
# result.manifest_path: Path
# result.schema_hash: str
# result.migrations_captured: int
# result.error: str (if failed)

# Load a baseline
result = baseline.load("v1.0.0")
# result.success: bool
# result.baseline_version: str
# result.migrations_faked: int
# result.migrations_remaining: int
# result.elapsed_seconds: float
# result.error: str (if failed)

# List all baselines
baselines: list[BaselineInfo] = baseline.list()
for info in baselines:
    print(f"{info.version}: {info.schema_hash}")
    print(f"  Created: {info.created_at}")
    print(f"  Migrations: {sum(len(v) for v in info.applied_migrations.values())}")

# Verify baseline integrity
valid, message = baseline.verify("v1.0.0")

# Delete a baseline
deleted = baseline.delete("v1.0.0")
```

### ParallelMigrationExecutor

```python
from django_matt.migration_tools import (
    ParallelMigrationExecutor,
    MigrationWavePlanner,
    format_parallel_result,
)

# Initialize executor
executor = ParallelMigrationExecutor(max_workers=4)

# Get execution plan
waves = executor.plan()
for i, wave in enumerate(waves):
    print(f"Wave {i+1}:")
    for app_label, migration_name in wave:
        print(f"  - {app_label}.{migration_name}")

# Execute (dry run)
result = executor.execute(dry_run=True)

# Execute for real
result = executor.execute()
# result.success: bool
# result.waves: list[WaveResult]
# result.total_elapsed: float
# result.sequential_would_take: float
# result.speedup_factor: float
# result.migrations_applied: int
# result.migrations_failed: int
# result.errors: list[str]

# Format for display
print(format_parallel_result(result))

# Use planner directly for analysis
planner = MigrationWavePlanner()
waves = planner.plan_waves()

# Estimate speedup with historical timing
timings = {
    ("accounts", "0086"): 1.5,
    ("products", "0065"): 2.3,
}
estimate = planner.estimate_speedup(timings)
print(f"Speedup: {estimate['speedup_factor']:.1f}x")
```

### MigrationProfiler

```python
from django_matt.migration_tools import (
    MigrationProfiler,
    MigrationTimer,
    format_project_stats,
    format_profiles,
)

profiler = MigrationProfiler()

# Get project-wide statistics
stats = profiler.get_project_stats()
# stats.total_migrations: int
# stats.applied_migrations: int
# stats.pending_migrations: int
# stats.total_operations: int
# stats.data_migrations_count: int
# stats.index_operations_count: int
# stats.estimated_pending_time: float
# stats.apps: dict[str, int]
# stats.complexity_breakdown: dict[str, int]

print(format_project_stats(stats))

# Profile pending migrations
profiles = profiler.profile_pending()
for profile in profiles:
    print(f"{profile.app_label}.{profile.migration_name}")
    print(f"  Complexity: {profile.estimated_complexity}")
    print(f"  Estimated: {profile.estimated_seconds}s")
    print(f"  Has data migration: {profile.has_data_migration}")
    print(f"  Has index creation: {profile.has_index_creation}")
    for warning in profile.warnings:
        print(f"  ⚠ {warning}")

print(format_profiles(profiles, limit=10))

# Profile a specific migration
profile = profiler.profile_migration("accounts", "0086_add_phone")

# Profile all migrations (not just pending)
all_profiles = profiler.profile_all()

# Timer for recording actual migration times
timer = MigrationTimer()

# Record timing
with timer.time_migration("accounts", "0086"):
    # Run migration here
    pass

# Get historical data
history = timer.get_history("accounts")
for entry in history:
    print(f"{entry.migration_name}: {entry.elapsed_seconds}s")

# Get slowest migrations
slowest = timer.get_slowest(10)
for migration_key, avg_time in slowest:
    print(f"{migration_key}: {avg_time:.2f}s average")

# Get average times for speedup estimation
averages = timer.get_average_times()
```

### SmartSquasher

```python
from django_matt.migration_tools import SmartSquasher, SquashPreview, SquashResult

squasher = SmartSquasher()

# Preview squash
preview: SquashPreview = squasher.preview("accounts", "0001", "0089")
# preview.app_label: str
# preview.from_migration: str
# preview.to_migration: str
# preview.migrations_to_squash: list[str]
# preview.total_operations: int
# preview.optimized_operations: int
# preview.has_run_python: bool
# preview.has_run_sql: bool
# preview.warnings: list[str]

print(f"Operations: {preview.total_operations} → {preview.optimized_operations}")
print(f"Migrations: {len(preview.migrations_to_squash)}")

# Execute squash
result: SquashResult = squasher.squash("accounts", "0001", "0089")
# result.success: bool
# result.app_label: str
# result.new_migration_name: str
# result.operations_before: int
# result.operations_after: int
# result.error: str (if failed)

# Dry run
result = squasher.squash("accounts", "0001", "0089", dry_run=True)
```

### MigrationAdvisor

```python
from django_matt.migration_tools import MigrationAdvisor, MigrationIssue

advisor = MigrationAdvisor()

# Analyze pending migrations
issues: list[MigrationIssue] = advisor.analyze_pending()

for issue in issues:
    print(f"{issue.severity.value}: {issue.app_label}/{issue.migration_name}")
    print(f"  {issue.operation_description}")
    print(f"  {issue.message}")

    if issue.rewrite:
        print("  Safe rewrite steps:")
        for step in issue.rewrite.steps:
            print(f"    - {step.description}")
            if step.sql:
                print(f"      {step.sql}")

# Analyze specific app
issues = advisor.analyze_app("accounts")
```

---

## Performance Benchmarks

Real-world measurements from a production codebase with 500+ migrations:

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| New dev setup | 127 min | 45 sec | **169x faster** |
| CI pipeline | 42 min | 3 min | **14x faster** |
| 20 pending migrations (sequential) | 8.5 min | - | baseline |
| 20 pending migrations (parallel) | 2.1 min | - | **4x faster** |
| Migration file loading | 12 sec | 3 sec | **4x faster** (after squash) |

### Baseline Load Times

| Database | Migrations | Schema Size | Load Time |
|----------|------------|-------------|-----------|
| PostgreSQL | 523 | 2.1 MB | 4.3s |
| MySQL | 523 | 1.8 MB | 5.1s |
| SQLite | 523 | 1.2 MB | 2.8s |

### Parallel Execution Speedup

| Scenario | Waves | Sequential | Parallel | Speedup |
|----------|-------|------------|----------|---------|
| 12 schema changes | 4 | 7.5s | 3.4s | 2.2x |
| 25 mixed migrations | 6 | 45s | 12s | 3.8x |
| 50 independent adds | 3 | 120s | 35s | 3.4x |
| 8 data migrations | 8 | 180s | 165s | 1.1x |

*Note: Data migrations (RunPython) often have implicit dependencies and can't be parallelized effectively.*

---

## Migration Strategy Decision Tree

```
                    ┌─────────────────────┐
                    │  How many pending   │
                    │    migrations?      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
           < 10           10 - 50            > 50
              │                │                │
              ▼                ▼                ▼
       ┌──────────┐     ┌──────────┐     ┌──────────┐
       │  Standard │     │ Profile  │     │ Create   │
       │  migrate  │     │  first   │     │ baseline │
       └──────────┘     └────┬─────┘     └──────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
              Has data           All schema
              migrations          changes
                    │                 │
                    ▼                 ▼
             ┌──────────┐      ┌──────────┐
             │ Consider │      │ Parallel │
             │ off-peak │      │ execute  │
             │ window   │      └──────────┘
             └──────────┘
```

---

## Summary

django-matt's migration acceleration tools transform a 2-hour migration nightmare into a 30-second setup:

1. **Baselines** — Skip running migrations entirely on fresh databases
2. **Parallel Execution** — Run independent migrations concurrently
3. **Profiling** — Understand what's slow before it becomes a problem
4. **Smart Squashing** — Reduce migration file count without changing schema
5. **Safety Analysis** — Catch dangerous patterns before production

Start with `python manage.py matt_migrate --stats` to understand your current state, then implement the strategies that fit your workflow.
