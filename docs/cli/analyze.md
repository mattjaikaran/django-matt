# Analysis Commands

Commands for analyzing and introspecting your Django Matt project.

## matt analyze

Run a full analysis of your Django project.

```bash
matt analyze [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | `false` | Output as JSON |

### Examples

```bash
# Full analysis
matt analyze

# JSON output
matt analyze --json
```

### Expected Output

```
Project Analysis

+-----------------+-------+
| Metric          | Value |
+-----------------+-------+
| Installed Apps  | 12    |
| Models          | 24    |
| Middleware      | 8     |
| Debug Mode      | Yes   |
+-----------------+-------+
```

---

## matt analyze models

List all Django models in your project.

```bash
matt analyze models [APP] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `APP` | Filter by app name (optional) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--fields`, `-f` | `false` | Show model fields |

### Examples

```bash
# List all models
matt analyze models

# List models for specific app
matt analyze models myapp

# Show fields
matt analyze models --fields

# Combine options
matt analyze models myapp --fields
```

### Expected Output

```
Django Models

myapp
-----
+---------+--------------+--------+
| Model   | Table        | Fields |
+---------+--------------+--------+
| User    | myapp_user   | 8      |
| Product | myapp_product| 12     |
| Order   | myapp_order  | 6      |
+---------+--------------+--------+

Total: 3 models in 1 apps
```

With `--fields`:

```
Django Models

myapp
-----
User
  - id
  - email
  - password
  - first_name
  - last_name
  - is_active
  - created_at
  - updated_at

Product
  - id
  - name
  - description
  - price
  ...
```

---

## matt analyze routes

List all API routes/endpoints in your project.

```bash
matt analyze routes [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--filter`, `-f` | None | Filter routes by pattern |
| `--method`, `-m` | None | Filter by HTTP method |

### Examples

```bash
# List all routes
matt analyze routes

# Filter by pattern
matt analyze routes --filter users

# Filter by method
matt analyze routes --method POST

# Combine filters
matt analyze routes --filter api --method GET
```

### Expected Output

```
API Routes

Found 24 routes
+---------+-------------------------+-----------------+------------------+
| Methods | Path                    | Name            | View             |
+---------+-------------------------+-----------------+------------------+
| GET     | /api/users/             | user-list       | UserController   |
| POST    | /api/users/             | user-create     | UserController   |
| GET     | /api/users/{id}/        | user-detail     | UserController   |
| PUT     | /api/users/{id}/        | user-update     | UserController   |
| DELETE  | /api/users/{id}/        | user-delete     | UserController   |
| GET     | /api/products/          | product-list    | ProductController|
| POST    | /api/products/          | product-create  | ProductController|
...
+---------+-------------------------+-----------------+------------------+
```

---

## matt routes

Alias for `matt analyze routes`. Quick way to list endpoints.

```bash
matt routes [OPTIONS]
```

### Examples

```bash
# List all routes
matt routes

# Filter by pattern
matt routes --filter auth
```

---

## matt endpoints

Alias for `matt analyze routes`. Another quick way to list endpoints.

```bash
matt endpoints [OPTIONS]
```

### Examples

```bash
matt endpoints --method POST
```

---

## matt status

Show project status and health information. Alias for `matt doctor`.

```bash
matt status
```

### Expected Output

Runs the same checks as `matt doctor`.

---

## matt doctor

Run comprehensive project diagnostics.

```bash
matt doctor [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--fix` | `false` | Attempt to fix issues |

### Checks Performed

1. **Django settings** - Can Django settings be loaded?
2. **Database connection** - Can we connect to the database?
3. **Required apps** - Are required Django apps installed?
4. **Security settings** - (Production only) Are security settings configured?
5. **Dependencies** - Are required Python packages installed?

### Examples

```bash
# Run diagnostics
matt doctor

# Try to fix issues
matt doctor --fix
```

### Expected Output

=== "All Passing"

    ```
    Project Health Check

    [check] Django settings
    [check] Database connection
    [check] Required apps
    [check] Dependencies

    +-------------------------------+
    | All checks passed!            |
    | Your project is healthy.      |
    +-------------------------------+
    ```

=== "With Issues"

    ```
    Project Health Check

    [check] Django settings
    [warning] Database connection: could not connect to server
    [check] Required apps
    [check] Dependencies

    +-------------------------------+
    | Some checks failed.           |
    | Review the warnings above.    |
    +-------------------------------+
    ```

---

## matt status info

Show detailed project information.

```bash
matt status info [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | `false` | Output as JSON |

### Examples

```bash
matt status info
```

### Expected Output

```
Project Information

Environment
-----------
+-------------+--------+
| Key         | Value  |
+-------------+--------+
| Python      | 3.12.0 |
| Django      | 5.2.0  |
| django-matt | 0.1.0  |
| Debug Mode  | Yes    |
+-------------+--------+

Project Stats
-------------
+----------------+-------+
| Metric         | Count |
+----------------+-------+
| Installed Apps | 12    |
| Models         | 24    |
| Middleware     | 8     |
+----------------+-------+

Database
--------
  default: postgresql - mydb
```

---

## matt status version

Show django-matt version.

```bash
matt status version
```

### Expected Output

```
Django Matt v0.1.0
```

---

## Use Cases

### Pre-Deployment Check

Before deploying, run diagnostics:

```bash
matt doctor
```

### API Documentation

List all endpoints for documentation:

```bash
matt routes > docs/api-endpoints.md
```

### Model Audit

Review all models in your project:

```bash
matt analyze models --fields > docs/models.md
```

### CI/CD Integration

Add health checks to CI:

```yaml
# .github/workflows/test.yml
- name: Project Health Check
  run: matt doctor

- name: List Routes
  run: matt routes
```

### Debugging

When debugging routing issues:

```bash
# Find all auth routes
matt routes --filter auth

# Find all POST endpoints
matt routes --method POST
```

---

## Programmatic Access

For scripts and automation, use JSON output:

```bash
# Models as JSON
matt analyze --json > project-info.json

# Parse with jq
matt analyze --json | jq '.models | length'
```

---

## Best Practices

!!! tip "Regular Health Checks"
    Run `matt doctor` regularly, especially after:
    - Adding new dependencies
    - Updating Django settings
    - Database configuration changes

!!! tip "Document Your API"
    Export routes for documentation:
    ```bash
    matt routes > API_ROUTES.md
    ```

!!! tip "CI Integration"
    Add health checks to your CI pipeline to catch issues early.

## See Also

- [Server Commands](serve.md)
- [Database Commands](database.md)
- [OpenAPI Documentation](../openapi/overview.md)
