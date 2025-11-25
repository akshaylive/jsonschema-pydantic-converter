"""Json schema to dynamic pydantic model."""

import inspect
from typing import Any, Type

from pydantic import BaseModel
from typing_extensions import deprecated

from ._schema_utils import collect_definitions
from ._transform_converter import TransformConverter


@deprecated(
    "Use create_type_adapter instead. Json schemas are better represented as type adapters as BaseModels can only represent 'objects'."
)
def transform(
    schema: dict[str, Any],
) -> Type[BaseModel]:
    """Convert a schema dict to a pydantic model.

    Args:
        schema: JSON schema.

    Returns: Pydantic model.

    Raises:
        ValueError: If the schema cannot be converted to a BaseModel (e.g., it's not an object type).
    """
    # Initialize namespace for type definitions
    namespace: dict[str, Any] = {}

    # Collect all definitions (top-level and nested)
    all_definitions = collect_definitions(schema)

    # Create type converter (using specialized version for transform)
    converter = TransformConverter(namespace)

    # Populate namespace with all definitions
    for name, definition in all_definitions.items():
        model = converter.convert(definition)
        # Use the full path as the key, but capitalize for consistency
        namespace[name.replace("/", "_").capitalize()] = model

    # Convert the main schema
    model = converter.convert(schema)

    # Ensure the result is a BaseModel
    if not (inspect.isclass(model) and issubclass(model, BaseModel)):
        raise ValueError(
            "Unable to convert schema to BaseModel. "
            "The schema must represent an object type. "
            "For non-object schemas, use create_type_adapter() instead."
        )

    model.model_rebuild(force=True, _types_namespace=namespace)
    return model
