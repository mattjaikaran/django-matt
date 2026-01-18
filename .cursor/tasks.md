{
  "version": "1.0.0",
  "tasks": {
    "init_project": {
      "command": "uv sync && uv run python manage.py migrate",
      "type": "shell",
      "group": "setup",
      "problemMatcher": []
    },
    "generate_crud": {
      "command": "uv run python manage.py generate_crud ${input:model} --full",
      "type": "shell",
      "group": "build",
      "problemMatcher": []
    },
    "generate_types": {
      "command": "uv run python manage.py sync_types --target typescript --output frontend/src/types",
      "type": "shell",
      "group": "build",
      "problemMatcher": ["$tsc"]
    },
    "watch_types": {
      "command": "uv run python manage.py sync_types --target typescript --output frontend/src/types --watch",
      "type": "shell",
      "group": "build",
      "isBackground": true,
      "problemMatcher": []
    },
    "test": {
      "command": "uv run pytest tests/ -v",
      "type": "shell",
      "group": "test",
      "problemMatcher": []
    },
    "lint": {
      "command": "uv run ruff check . --fix && uv run ruff format .",
      "type": "shell",
      "group": "build",
      "problemMatcher": []
    },
    "dev_server": {
      "command": "uv run python manage.py runserver",
      "type": "shell",
      "group": "build",
      "isBackground": true,
      "problemMatcher": []
    }
  },
  "inputs": [
    {
      "id": "model",
      "type": "promptString",
      "description": "Model path (e.g., myapp.MyModel)"
    }
  ]
}
