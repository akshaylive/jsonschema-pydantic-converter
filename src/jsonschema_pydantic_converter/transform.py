"""Json schema to dynamic pydantic model."""

from typing import Any, Tuple, Type

from pydantic import BaseModel, RootModel

from .create_type_adapter import create_type_adapter


def transform(
    schema: dict[str, Any],
) -> Type[BaseModel]:
    """Convert a JSON schema dict to a Pydantic model.

    Args:
        schema: JSON schema dictionary following the JSON Schema specification.
                Non-object types are converted into `RootModel`.

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
    return transform_with_modules(schema)[0]


def transform_with_modules(
    schema: dict[str, Any],
) -> Tuple[type[BaseModel], dict[str, Any]]:
    """Convert a JSON schema dict to a Pydantic model with its namespace.

    This function is similar to `transform()` but also returns the namespace
    dictionary containing all generated types, which can be useful for
    programmatic inspection or custom type resolution.

    Args:
        schema: JSON schema dictionary following the JSON Schema specification.
                Non-object types are converted into `RootModel`.

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

    type_adapter = create_type_adapter(schema, _namespace=namespace)
    inner_type = type_adapter._type

    model: type[BaseModel]
    if isinstance(inner_type, type) and issubclass(inner_type, BaseModel):
        model = inner_type
    else:
        model = RootModel.__class_getitem__(inner_type)  # type: ignore[assignment]

    model.model_rebuild(_types_namespace=namespace)

    return (model, namespace)
