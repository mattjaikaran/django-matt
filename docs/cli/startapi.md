# startapi Command

Initialize a new Django Matt project.

## Usage

```bash
python manage.py startapi myproject
```

## Options

| Option | Description |
|--------|-------------|
| `--template` | Project template (`minimal`, `b2b`, `saas`) |
| `--auth` | Auth type (`jwt`, `session`, `both`) |
| `--docker` | Include Docker configuration |
| `--frontend` | Frontend framework (`react`, `svelte`, `none`) |

## Examples

```bash
# Minimal API
python manage.py startapi myapi

# B2B with organizations
python manage.py startapi myapi --template b2b --auth jwt

# Full stack with React
python manage.py startapi myapi --template saas --frontend react --docker
```
