# startapi Command

!!! note "Comprehensive Documentation"
    For complete documentation, see [Management: startapi](../management/startapi.md).

## Quick Reference

Initialize a new Django Matt project:

```bash
# Basic project
python manage.py startapi myproject

# B2B with organizations
python manage.py startapi myproject --template b2b --auth jwt

# Full stack with React and Docker
python manage.py startapi myproject --template b2b --frontend react-vite --docker
```

## CLI Equivalent

```bash
matt new api myproject --template b2b --auth jwt --docker
```

## Options Summary

| Option | Default | Description |
|--------|---------|-------------|
| `--template`, `-t` | `starter` | Template: `starter`, `b2b`, `b2c` |
| `--auth`, `-a` | `jwt` | Auth: `none`, `jwt`, `magic-link`, `oauth`, `all` |
| `--frontend`, `-f` | `none` | Frontend: `none`, `react-vite`, `swift` |
| `--docker` | `false` | Include Docker configuration |
| `--db` | `postgres` | Database: `postgres`, `mysql`, `sqlite` |
| `--with-example` | `false` | Include example code |

## See Also

- [Complete startapi Documentation](../management/startapi.md)
- [CLI: matt new api](generate.md#matt-new-api)
- [Templates Guide](../templates.md)
