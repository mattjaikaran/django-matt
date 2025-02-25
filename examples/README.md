# Django Matt Examples

This directory contains example applications that demonstrate the features and capabilities of the Django Matt framework.

## Available Examples

### 1. Todo App Example

A simple Todo application that demonstrates the basic features of Django Matt:
- API router setup
- Controller-based views
- Pydantic schema integration
- CRUD operations

**Location:** `examples/todo_app.py`

**To run:**
```bash
python examples/todo_app.py
```

### 2. Error Handling Demo

Demonstrates Django Matt's advanced error handling capabilities:
- Detailed error messages
- Traceback formatting
- Validation error handling
- Custom error middleware

**Location:** `examples/error_handling_demo.py`

**To run:**
```bash
python examples/error_handling_demo.py
```

### 3. Hot Reloading Demo

Shows how to use Django Matt's hot reloading feature:
- Automatic code reloading without server restart
- WebSocket-based browser refresh
- File change detection

**Location:** `examples/hot_reload_demo.py`

**To run:**
```bash
python examples/hot_reload_demo.py
```

## Prerequisites

Before running the examples, make sure you have installed Django Matt and its dependencies:

```bash
# Install Django Matt from the local directory
pip install -e .

# Or install required dependencies
pip install django pydantic websockets
```

## Usage Tips

1. Each example is a standalone application that can be run directly with Python.
2. The examples are designed to be simple and easy to understand.
3. Look at the code comments for detailed explanations of how each feature works.
4. Modify the examples to experiment with different configurations and features.

## Additional Resources

- Check the main [Django Matt documentation](../README.md) for more information.
- See the [todos.md](../todos.md) file for the development roadmap. 