# jsonschema-to-pydantic

[![CI](https://github.com/akshaylive/jsonschema-to-pydantic/workflows/CI/badge.svg)](https://github.com/akshaylive/jsonschema-to-pydantic/actions)
[![PyPI](https://img.shields.io/pypi/v/jsonschema-to-pydantic.svg)](https://pypi.org/project/jsonschema-to-pydantic/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jsonschema-to-pydantic.svg)](https://pypi.org/project/jsonschema-to-pydantic/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Convert JSON Schema definitions to Pydantic models dynamically at runtime.

## Overview

`jsonschema-to-pydantic` is a Python library that transforms JSON Schema dictionaries into Pydantic v2 models. This is useful when you need to work with dynamic schemas, validate data against JSON Schema specifications, or bridge JSON Schema-based systems with Pydantic-based applications.

## Features

- **Dynamic Model Generation**: Convert JSON Schema to Pydantic models at runtime
- **Comprehensive Type Support**:
  - Primitive types (string, number, integer, boolean, null)
  - Arrays with typed items
  - Nested objects
  - Enums
  - Union types (anyOf)
  - Combined schemas (allOf)
- **Schema References**: Support for `$ref` and `$defs`/`definitions`
- **Field Metadata**: Preserves titles, descriptions, and default values
- **Self-References**: Handle recursive schema definitions
- **Pydantic v2 Compatible**: Built for Pydantic 2.0+

## Installation

```bash
pip install jsonschema-to-pydantic
```

Or using uv:

```bash
uv add jsonschema-to-pydantic
```

## Usage

### Basic Example

```python
from jsonschema_to_pydantic import transform

# Define a JSON Schema
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "User's name"},
        "age": {"type": "integer", "description": "User's age"},
        "email": {"type": "string"}
    },
    "required": ["name", "age"]
}

# Convert to Pydantic model
UserModel = transform(schema)

# Use the model
user = UserModel(name="John Doe", age=30, email="john@example.com")
print(user.model_dump())
# {'name': 'John Doe', 'age': 30, 'email': 'john@example.com'}
```

### Working with Enums

```python
schema = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["active", "inactive", "pending"]
        }
    }
}

StatusModel = transform(schema)
obj = StatusModel(status="active")
```

### Nested Objects

```python
schema = {
    "type": "object",
    "properties": {
        "user": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"}
            },
            "required": ["name"]
        }
    }
}

Model = transform(schema)
data = Model(user={"name": "Alice", "email": "alice@example.com"})
```

### Arrays

```python
schema = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

TagsModel = transform(schema)
obj = TagsModel(tags=["python", "pydantic", "json-schema"])
```

### Schema with References

```python
schema = {
    "type": "object",
    "properties": {
        "person": {"$ref": "#/$defs/Person"}
    },
    "$defs": {
        "Person": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }
    }
}

Model = transform(schema)
person = Model(person={"name": "Bob", "age": 25})
```

### Union Types (anyOf)

```python
schema = {
    "type": "object",
    "properties": {
        "value": {
            "anyOf": [
                {"type": "string"},
                {"type": "integer"}
            ]
        }
    }
}

Model = transform(schema)
obj1 = Model(value="text")
obj2 = Model(value=42)
```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Clone the Repository

```bash
git clone https://github.com/akshaylive/jsonschema-to-pydantic.git
cd jsonschema-to-pydantic
```

### Install Dependencies

Using uv (recommended):

```bash
uv sync
```

Using pip:

```bash
pip install -e .
pip install mypy ruff pytest pytest-cov
```

### Run Tests

```bash
# Using uv
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=html

# Using pytest directly (if in activated venv)
pytest
```

### Code Quality

The project uses several tools to maintain code quality:

```bash
# Type checking with mypy
uv run mypy src/

# Linting with ruff
uv run ruff check .

# Format code with ruff
uv run ruff format .
```

## Contributing

Contributions are welcome! Here's how you can help:

### Reporting Issues

- Check existing issues before creating a new one
- Provide a clear description of the problem
- Include a minimal reproducible example
- Specify your Python and Pydantic versions

### Submitting Pull Requests

1. Fork the repository
2. Create a new branch for your feature/fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes and ensure:
   - All tests pass: `uv run pytest`
   - Code is properly formatted: `uv run ruff format .`
   - No linting errors: `uv run ruff check .`
   - Type checking passes: `uv run mypy src/`
4. Add tests for new functionality
5. Update documentation if needed
6. Commit your changes with clear commit messages
7. Push to your fork and submit a pull request

### Code Style

- Follow PEP 8 guidelines
- Use Google-style docstrings
- Type hints are required for all functions
- Line length: 88 characters (Black/Ruff default)

### Development Guidelines

- Write tests for all new features
- Maintain backwards compatibility when possible
- Update the README for user-facing changes
- Keep dependencies minimal

## Limitations

- Optional fields without defaults are set to `None` rather than using `Optional[T]` type annotation to maintain JSON Schema round-trip consistency
- Complex schema combinations may require testing for edge cases

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Maintainer

Akshaya Shanbhogue - [akshay.live@gmail.com](mailto:akshay.live@gmail.com)

## Links

- [GitHub Repository](https://github.com/akshaylive/jsonschema-to-pydantic)
- [Issue Tracker](https://github.com/akshaylive/jsonschema-to-pydantic/issues)
