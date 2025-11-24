# jsonschema-pydantic-converter

[![CI](https://github.com/akshaylive/jsonschema-pydantic-converter/workflows/CI/badge.svg)](https://github.com/akshaylive/jsonschema-pydantic-converter/actions)
[![PyPI](https://img.shields.io/pypi/v/jsonschema-pydantic-converter.svg)](https://pypi.org/project/jsonschema-pydantic-converter/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jsonschema-pydantic-converter.svg)](https://pypi.org/project/jsonschema-pydantic-converter/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Convert JSON Schema definitions to Pydantic models dynamically at runtime.

## Overview

`jsonschema-pydantic-converter` is a Python library that transforms JSON Schema dictionaries into Pydantic v2 models. This is useful when you need to work with dynamic schemas, validate data against JSON Schema specifications, or bridge JSON Schema-based systems with Pydantic-based applications.

## Features

- **Dynamic Model Generation**: Convert JSON Schema to Pydantic models at runtime
- **TypeAdapter Support**: Generate TypeAdapters for enhanced validation and serialization
- **Comprehensive Type Support**:
  - Primitive types (string, number, integer, boolean, null)
  - Arrays with typed items and tuples (prefixItems)
  - Nested objects
  - Enums (with and without explicit type)
  - Union types (anyOf, oneOf)
  - Combined schemas (allOf)
  - Negation (not)
  - Constant values (const)
  - Boolean schemas (true/false)
- **Validation Constraints**: Full support for Pydantic-native constraints
  - String: minLength, maxLength, pattern
  - Numeric: minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf
  - Array: minItems, maxItems
- **Schema References**: Support for `$ref` and `$defs`/`definitions`
- **Field Metadata**: Preserves titles, descriptions, and default values
- **Self-References**: Handle recursive schema definitions
- **Pydantic v2 Compatible**: Built for Pydantic 2.0+

## Installation

```bash
pip install jsonschema-pydantic-converter
```

Or using uv:

```bash
uv add jsonschema-pydantic-converter
```

## Usage

> **Note on Deprecation**: The `transform()` function is deprecated in favor of `create_type_adapter()`. JSON schemas are better represented as TypeAdapters since BaseModels can only represent 'object' types, while TypeAdapters can handle any JSON schema type including primitives, arrays, and unions. Existing code using `transform()` will continue to work, but new code should use `create_type_adapter()`.

### Basic Example (Deprecated - using `transform`)

```python
from jsonschema_pydantic_converter import transform

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

# Convert to Pydantic model (deprecated - use create_type_adapter instead)
UserModel = transform(schema)

# Use the model
user = UserModel(name="John Doe", age=30, email="john@example.com")
print(user.model_dump())
# {'name': 'John Doe', 'age': 30, 'email': 'john@example.com'}
```

### Using TypeAdapter for Validation

The `create_type_adapter` function returns a Pydantic TypeAdapter, which provides additional validation and serialization capabilities:

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "email": {"type": "string"}
    },
    "required": ["name", "age"]
}

# Create TypeAdapter
adapter = create_type_adapter(schema)

# Validate Python objects
user = adapter.validate_python({"name": "John Doe", "age": 30, "email": "john@example.com"})
print(user)

# Validate JSON strings directly
json_str = '{"name": "Jane Doe", "age": 25}'
user = adapter.validate_json(json_str)

# Serialize back to Python dict
user_dict = adapter.dump_python(user)
print(user_dict)
# {'name': 'Jane Doe', 'age': 25, 'email': None}
```

**When to use `transform` vs `create_type_adapter`:**
- **Recommended**: Use `create_type_adapter()` for all new code - it handles any JSON schema type and provides validation/serialization methods
- **Deprecated**: `transform()` is maintained for backward compatibility but only works with object schemas. It returns a BaseModel class if you need direct model access

### Working with Enums

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["active", "inactive", "pending"]
        }
    }
}

adapter = create_type_adapter(schema)
obj = adapter.validate_python({"status": "active"})
```

### Nested Objects

```python
from jsonschema_pydantic_converter import create_type_adapter

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

adapter = create_type_adapter(schema)
data = adapter.validate_python({"user": {"name": "Alice", "email": "alice@example.com"}})
```

### Arrays

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

adapter = create_type_adapter(schema)
obj = adapter.validate_python({"tags": ["python", "pydantic", "json-schema"]})
```

### Schema with References

```python
from jsonschema_pydantic_converter import create_type_adapter

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

adapter = create_type_adapter(schema)
person = adapter.validate_python({"person": {"name": "Bob", "age": 25}})
```

### Union Types (anyOf)

```python
from jsonschema_pydantic_converter import create_type_adapter

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

adapter = create_type_adapter(schema)
obj1 = adapter.validate_python({"value": "text"})
obj2 = adapter.validate_python({"value": 42})
```

### Validation Constraints

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "type": "object",
    "properties": {
        "username": {
            "type": "string",
            "minLength": 3,
            "maxLength": 20,
            "pattern": "^[a-z0-9_]+$"
        },
        "age": {
            "type": "integer",
            "minimum": 0,
            "maximum": 150
        },
        "score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "multipleOf": 0.5
        }
    }
}

adapter = create_type_adapter(schema)
# Valid data
obj = adapter.validate_python({
    "username": "john_doe",
    "age": 25,
    "score": 85.5
})

# Invalid - will raise ValidationError
# adapter.validate_python({"username": "ab"})  # Too short
# adapter.validate_python({"age": -1})  # Below minimum
```

### Constant Values (const)

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "type": "object",
    "properties": {
        "country": {"const": "United States"},
        "version": {"const": 1}
    }
}

adapter = create_type_adapter(schema)
# Valid - exact match
obj = adapter.validate_python({"country": "United States", "version": 1})

# Invalid - will raise ValidationError
# adapter.validate_python({"country": "Canada", "version": 1})
```

### Negation (not)

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "type": "object",
    "properties": {
        "value": {"not": {"type": "string"}}
    }
}

adapter = create_type_adapter(schema)
# Valid - not a string
obj1 = adapter.validate_python({"value": 42})
obj2 = adapter.validate_python({"value": [1, 2, 3]})

# Invalid - is a string
# adapter.validate_python({"value": "text"})
```

### Combined Schemas (allOf)

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "allOf": [
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        },
        {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
            "required": ["age"]
        }
    ]
}

adapter = create_type_adapter(schema)
# Valid - satisfies all schemas
obj = adapter.validate_python({"name": "Alice", "age": 30})

# Invalid - missing required fields
# adapter.validate_python({"name": "Alice"})
```

### Tuples (prefixItems)

```python
from jsonschema_pydantic_converter import create_type_adapter

schema = {
    "type": "array",
    "prefixItems": [
        {"type": "string"},
        {"type": "integer"},
        {"type": "boolean"}
    ]
}

adapter = create_type_adapter(schema)
# Valid tuple
result = adapter.validate_python(["hello", 42, True])
# Returns: ("hello", 42, True)
```

### Boolean Schemas

```python
from jsonschema_pydantic_converter import create_type_adapter

# Schema that accepts anything
schema_true = True
adapter_true = create_type_adapter(schema_true)
adapter_true.validate_python("anything")  # Valid
adapter_true.validate_python(42)  # Valid
adapter_true.validate_python([1, 2, 3])  # Valid

# Schema that rejects everything
schema_false = False
adapter_false = create_type_adapter(schema_false)
# adapter_false.validate_python("anything")  # Invalid - raises ValidationError
```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Clone the Repository

```bash
git clone https://github.com/akshaylive/jsonschema-pydantic-converter.git
cd jsonschema-pydantic-converter
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
- When `allOf` contains `$ref` references, the generated `json_schema()` output may not preserve the exact original structure (validation still works correctly)
- Some advanced JSON Schema features are not yet supported:
  - `$anchor` references (causes syntax errors with forward references)
  - `$dynamicRef` / `$dynamicAnchor` (draft 2020-12 advanced features)
  - Full enforcement of: `uniqueItems`, `contains`, `propertyNames`, `patternProperties`, `format` validation
  - `if-then-else` conditionals (base type is used, but conditionals are not enforced)
- Complex schema combinations may require testing for edge cases

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Maintainer

Akshaya Shanbhogue - [akshay.live@gmail.com](mailto:akshay.live@gmail.com)

## Links

- [GitHub Repository](https://github.com/akshaylive/jsonschema-pydantic-converter)
- [Issue Tracker](https://github.com/akshaylive/jsonschema-pydantic-converter/issues)
