{
  "version": "1.0.0",
  "tasks": {
    "init_project": {
      "command": "uv env && uv pip install django pydantic && pixi init",
      "type": "shell",
      "group": "setup",
      "problemMatcher": []
    },
    "generate_types": {
      "command": "python manage.py generate_types && pnpm -C frontend gen:types",
      "type": "shell",
      "group": "build",
      "problemMatcher": ["$tsc"]
    }
  }
}