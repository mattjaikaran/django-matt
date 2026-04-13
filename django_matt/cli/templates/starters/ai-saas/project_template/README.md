# {{ project_name }}

AI-powered SaaS built with [django-matt](https://github.com/mattjaikaran/django-matt).

## Features

- LLM conversation threads (Anthropic/OpenAI)
- Document upload and RAG indexing
- Stripe billing with tiered rate limiting
- Background tasks via Celery
- WebSocket support for streaming responses

## Quick Start

```bash
uv sync
docker compose up db redis -d
uv run python manage.py migrate
uv run python manage.py runserver
```

## With Docker (full stack)

```bash
docker compose up -d
docker compose exec api python manage.py migrate
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `OPENAI_API_KEY` | OpenAI API key (optional) |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |

## Testing

```bash
uv run pytest tests/ -x -q
```
