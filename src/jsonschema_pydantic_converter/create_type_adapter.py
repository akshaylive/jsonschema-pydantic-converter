"""Convert JSON Schema definitions to Pydantic TypeAdapters with dynamically generated models.

This module provides functionality to transform JSON Schema dictionaries into Pydantic v2
models at runtime, wrapped in TypeAdapters for validation and serialization.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, TypeAdapter

from ._schema_utils import collect_definitions
from ._type_converters import TypeConverter


def create_type_adapter(
    schema: dict[str, Any] | bool,
) -> TypeAdapter[Any]:
    """Convert a JSON Schema dict to a Pydantic TypeAdapter.

    This function dynamically generates Pydantic models from JSON Schema definitions
    and returns a TypeAdapter that wraps the generated model. The TypeAdapter provides
    methods for validation and serialization.

    Args:
        schema: JSON schema dictionary following the JSON Schema specification.
                Supports primitive types, objects, arrays, enums, references ($ref),
                and schema composition (allOf, anyOf, oneOf, not).
                Can also be a boolean (true accepts all, false rejects all).

    Returns:
        A Pydantic TypeAdapter wrapping the dynamically generated model.
        Use adapter.validate_python(data) to validate Python objects,
        adapter.validate_json(json_str) to validate JSON strings, and
        adapter.dump_python(obj) to serialize validated objects.

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "name": {"type": "string"},
        ...         "age": {"type": "integer"}
        ...     },
        ...     "required": ["name"]
        ... }
        >>> adapter = create_type_adapter(schema)
        >>> obj = adapter.validate_python({"name": "Alice", "age": 30})
    """
    # Handle boolean schemas
    if isinstance(schema, bool):
        if schema is True:
            # true schema accepts everything
            return TypeAdapter(Any)
        else:
            # false schema rejects everything
            def reject_all(value: Any) -> Any:
                raise ValueError("Schema is false - no values are valid")

            return TypeAdapter(Annotated[Any, BeforeValidator(reject_all)])

    # Initialize namespace for type definitions
    namespace: dict[str, Any] = {}

    # Collect all definitions (top-level and nested)
    all_definitions = collect_definitions(schema)

    # Create type converter
    converter = TypeConverter(namespace)

    # Populate namespace with all definitions
    for name, definition in all_definitions.items():
        model = converter.convert(definition)
        # Use the full path as the key, but capitalize for consistency
        namespace[name.replace("/", "_").capitalize()] = model

    # Convert the main schema
    model = converter.convert(schema)
    type_adapter = TypeAdapter(model)
    type_adapter.rebuild(force=True, _types_namespace=namespace)
    return type_adapter
