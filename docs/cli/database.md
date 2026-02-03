# Database Commands

Commands for managing database migrations, data seeding, and maintenance.

## matt db migrate

Run database migrations to apply schema changes.

```bash
matt db migrate [APP_LABEL] [MIGRATION_NAME] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `APP_LABEL` | App to migrate (optional, migrates all if omitted) |
| `MIGRATION_NAME` | Specific migration to migrate to (optional) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--fake` | `false` | Mark migrations as run without executing |
| `--plan` | `false` | Show migration plan without running |

### Examples

```bash
# Run all pending migrations
matt db migrate

# Migrate specific app
matt db migrate myapp

# Migrate to specific migration
matt db migrate myapp 0005_add_email_field

# Show migration plan
matt db migrate --plan

# Mark migrations as already run
matt db migrate myapp --fake
```

### Expected Output

```
Running migrations...

Operations to perform:
  Apply all migrations: admin, auth, contenttypes, myapp, sessions
Running migrations:
  Applying myapp.0006_add_status_field... OK
  Applying myapp.0007_create_index... OK
```

---

## matt db make

Create new database migrations based on model changes.

```bash
matt db make [APP_LABEL] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `APP_LABEL` | App to make migrations for (optional) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--name`, `-n` | Auto-generated | Migration name |
| `--empty` | `false` | Create an empty migration |
| `--merge` | `false` | Enable merge mode for conflicting migrations |
| `--dry-run` | `false` | Show what would be created without writing |

### Examples

```bash
# Auto-detect and create migrations
matt db make

# Create migration for specific app
matt db make myapp

# Create with custom name
matt db make myapp --name add_user_preferences

# Create empty migration for data migrations
matt db make myapp --empty --name populate_defaults

# Dry run to preview
matt db make --dry-run
```

### Expected Output

```
Creating migrations...

Migrations for 'myapp':
  myapp/migrations/0008_add_preferences.py
    - Add field preferences to user
    - Add field notification_settings to user
```

!!! tip "Data Migrations"
    For data migrations (not schema changes), use `--empty`:
    ```bash
    matt db make myapp --empty --name migrate_user_data
    ```
    Then edit the generated file to add `RunPython` operations.

---

## matt db show

Show the status of all migrations.

```bash
matt db show [APP_LABEL] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `APP_LABEL` | Filter by app (optional) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--list`, `-l` | `false` | Show in list format |

### Examples

```bash
# Show all migrations
matt db show

# Show for specific app
matt db show myapp

# List format
matt db show --list
```

### Expected Output

```
Migration Status

admin
 [X] 0001_initial
 [X] 0002_logentry_remove_auto_add
 [X] 0003_logentry_add_action_flag_choices
auth
 [X] 0001_initial
 [X] 0002_alter_permission_name_max_length
 ...
myapp
 [X] 0001_initial
 [X] 0002_add_created_at
 [ ] 0003_add_status_field  <-- Pending
```

---

## matt db reset

Reset the database by flushing all data.

```bash
matt db reset [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--yes`, `-y` | `false` | Skip confirmation prompt |
| `--keep-migrations` | `false` | Keep migration files |

### Examples

```bash
# Reset with confirmation
matt db reset

# Skip confirmation (dangerous!)
matt db reset --yes
```

### Expected Output

```
WARNING: This will delete all data in the database!
Are you sure you want to continue? [y/N]: y

Resetting database...

Database reset complete!
```

!!! danger "Data Loss"
    This command **permanently deletes all data**. Use with extreme caution.
    Never run in production without backups.

---

## matt db seed

Seed the database with initial or test data.

```bash
matt db seed [APP_LABEL] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `APP_LABEL` | App to seed (optional) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--fixture`, `-f` | None | Specific fixture file to load |

### Examples

```bash
# Run seed command (if defined)
matt db seed

# Load specific fixture
matt db seed --fixture initial_data.json

# Seed specific app
matt db seed myapp
```

### Expected Output

```
Seeding database...

Installed 42 object(s) from 1 fixture(s)
```

!!! tip "Creating Fixtures"
    Create fixtures from existing data:
    ```bash
    matt db dump --output fixtures/seed_data.json
    ```

---

## matt db dump

Export database data to a fixture file.

```bash
matt db dump [APP_LABEL] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `APP_LABEL` | App to dump (optional, dumps all if omitted) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `dump.json` | Output file path |
| `--indent` | `2` | JSON indentation |
| `--natural-foreign` | `false` | Use natural foreign keys |
| `--natural-primary` | `false` | Use natural primary keys |

### Examples

```bash
# Dump entire database
matt db dump

# Dump specific app
matt db dump myapp

# Custom output file
matt db dump --output backup/data_2024.json

# With natural keys (better for portability)
matt db dump --natural-foreign --natural-primary
```

### Expected Output

```
Dumping database to backup.json...

Data dumped to backup.json
```

---

## matt db shell_db

Open the database shell (psql, sqlite3, etc.).

```bash
matt db shell_db [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--database`, `-d` | `default` | Database alias to connect to |

### Examples

```bash
# Open default database shell
matt db shell_db

# Open specific database
matt db shell_db --database replica
```

---

## matt db squash

Squash multiple migrations into a single migration.

```bash
matt db squash APP_LABEL [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `APP_LABEL` | App to squash migrations for (required) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--start` | None | Start migration name |
| `--end` | None | End migration name |

### Examples

```bash
# Squash all migrations for an app
matt db squash myapp

# Squash specific range
matt db squash myapp --start 0001 --end 0010
```

### Expected Output

```
Squashing migrations for myapp...

Will squash the following migrations:
 - 0001_initial
 - 0002_add_field
 - 0003_add_index
 - 0004_update_model
 - 0005_add_constraints

Created new squashed migration:
  myapp/migrations/0001_squashed_0005_add_constraints.py
```

---

## Common Workflows

### Fresh Database Setup

```bash
# 1. Create migrations (if needed)
matt db make

# 2. Apply migrations
matt db migrate

# 3. Create superuser
python manage.py createsuperuser

# 4. Seed initial data
matt db seed --fixture initial_data.json
```

### Handling Migration Conflicts

```bash
# When multiple developers create migrations:
matt db make --merge

# This creates a merge migration resolving conflicts
```

### Rolling Back Migrations

```bash
# Roll back to specific migration
matt db migrate myapp 0005

# Roll back all migrations for an app
matt db migrate myapp zero
```

### Database Backup/Restore

```bash
# Backup
matt db dump --output backup_$(date +%Y%m%d).json

# Restore
matt db seed --fixture backup_20240301.json
```

## Best Practices

!!! tip "Migration Naming"
    Use descriptive migration names:
    ```bash
    matt db make myapp --name add_user_email_verification
    ```

!!! tip "Review Before Applying"
    Always review migration plans:
    ```bash
    matt db migrate --plan
    ```

!!! warning "Production Migrations"
    For production, always:

    1. Backup the database first
    2. Review the migration SQL
    3. Run during low-traffic periods
    4. Have a rollback plan

## See Also

- [Django Migrations Documentation](https://docs.djangoproject.com/en/stable/topics/migrations/)
- [Database Configuration](../database.md)
- [Server Commands](serve.md)
