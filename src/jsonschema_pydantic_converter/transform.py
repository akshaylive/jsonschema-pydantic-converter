"""Json schema to dynamic pydantic model."""

import inspect
from typing import Any, Tuple, Type, get_args, get_origin

from pydantic import BaseModel

from .create_type_adapter import create_type_adapter


def transform(
    schema: dict[str, Any],
) -> Type[BaseModel]:
    """Convert a JSON schema dict to a Pydantic model.

    Args:
        schema: JSON schema dictionary following the JSON Schema specification.
                Must represent an object type.

    Returns:
        A Pydantic BaseModel class generated from the schema.

    Raises:
        ValueError: If the schema cannot be converted to a BaseModel
                   (e.g., it's not an object type).

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "name": {"type": "string"},
        ...         "age": {"type": "integer"}
        ...     }
        ... }
        >>> Model = transform(schema)
        >>> instance = Model(name="Alice", age=30)
    """
    return transform_with_model(schema)[0]


def transform_with_model(
    schema: dict[str, Any],
) -> Tuple[type[BaseModel], dict[str, Any]]:
    """Convert a JSON schema dict to a Pydantic model with its namespace.

    This function is similar to `transform()` but also returns the namespace
    dictionary containing all generated types, which can be useful for
    programmatic inspection or custom type resolution.

    Args:
        schema: JSON schema dictionary following the JSON Schema specification.
                Must represent an object type.

    Returns:
        A tuple containing:
        - The Pydantic BaseModel class generated from the schema
        - A dictionary mapping type names to their generated Pydantic types

    Raises:
        ValueError: If the schema cannot be converted to a BaseModel
                   (e.g., it's not an object type).

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "user": {"$ref": "#/definitions/User"}
        ...     },
        ...     "definitions": {
        ...         "User": {
        ...             "type": "object",
        ...             "properties": {"name": {"type": "string"}}
        ...         }
        ...     }
        ... }
        >>> Model, namespace = transform_with_model(schema)
        >>> # namespace contains {"User": <generated User model>}
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
    return (model, namespace)
