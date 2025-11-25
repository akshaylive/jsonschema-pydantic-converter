"""Json schema to dynamic pydantic model."""

import inspect
from typing import Any, Type, get_args, get_origin

from pydantic import BaseModel
from typing_extensions import deprecated

from .create_type_adapter import create_type_adapter


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
    # Create a namespace that will be populated by create_type_adapter
    namespace: dict[str, Any] = {}

    # Use create_type_adapter and extract the underlying type
    type_adapter = create_type_adapter(schema, _namespace=namespace)
    model = type_adapter._type

    # Handle Annotated types - extract the actual type
    origin = get_origin(model)
    if origin is not None:
        # For Annotated[X, ...], get X
        args = get_args(model)
        if args:
            model = args[0]

    # Ensure the result is a BaseModel
    if not (inspect.isclass(model) and issubclass(model, BaseModel)):
        raise ValueError(
            "Unable to convert schema to BaseModel. "
            "The schema must represent an object type. "
            "For non-object schemas, use create_type_adapter() instead."
        )

    # Rebuild the model with the namespace so it can resolve forward references
    # This allows model_json_schema() to work properly with $refs/$defs
    model.model_rebuild(_types_namespace=namespace)

    return model
