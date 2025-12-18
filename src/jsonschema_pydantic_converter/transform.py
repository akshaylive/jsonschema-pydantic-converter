"""Json schema to dynamic pydantic model."""

import inspect
import sys
from types import ModuleType
from typing import Any, Type, get_args, get_origin

from pydantic import BaseModel
from typing_extensions import deprecated

from .create_type_adapter import create_type_adapter

# Shared pseudo-module for all dynamically created types
# This allows get_type_hints() to resolve forward references
_DYNAMIC_MODULE_NAME = "jsonschema_pydantic_converter._dynamic"

def _get_or_create_dynamic_module() -> ModuleType:
    """Get or create the shared pseudo-module for dynamic types."""
    if _DYNAMIC_MODULE_NAME not in sys.modules:
        pseudo_module = ModuleType(_DYNAMIC_MODULE_NAME)
        pseudo_module.__doc__ = "Shared module for dynamically generated Pydantic models from JSON schemas"
        sys.modules[_DYNAMIC_MODULE_NAME] = pseudo_module
    return sys.modules[_DYNAMIC_MODULE_NAME]


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

    # After rebuild, create a corrected namespace that maps type names to the
    # actual type objects used in field annotations (rebuild may create new instances)
    corrected_namespace: dict[str, Any] = {}

    def collect_types(annotation: Any) -> None:
        """Recursively collect all BaseModel types from an annotation."""
        # Unwrap generic types like List, Optional, etc.
        origin = get_origin(annotation)
        if origin is not None:
            for arg in get_args(annotation):
                collect_types(arg)
        
        elif inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            # Find the original name for this type from the namespace
            for type_name, type_def in namespace.items():
                # Match by class name since rebuild may create new instances
                if (hasattr(annotation, '__name__') and
                    hasattr(type_def, '__name__') and
                    annotation.__name__ == type_def.__name__):
                    # Store the actual annotation type, not the old namespace one
                    corrected_namespace[type_name] = annotation
                    break

    # Collect all types from field annotations
    for field_info in model.model_fields.values():
        collect_types(field_info.annotation)

    # Get the shared pseudo-module and populate it with this schema's types
    # This ensures that forward references can be resolved by get_type_hints()
    # when the model is used with external libraries (e.g., LangGraph)
    pseudo_module = _get_or_create_dynamic_module()

    # Populate the pseudo-module with all types from the namespace
    # Use the original names so forward references resolve correctly
    for type_name, type_def in corrected_namespace.items():
        setattr(pseudo_module, type_name, type_def)

    setattr(pseudo_module, model.__name__, model)

    # Update the model's __module__ to point to the shared pseudo-module
    model.__module__ = _DYNAMIC_MODULE_NAME

    # Update the __module__ of all generated types in the namespace
    for type_def in corrected_namespace.values():
        if inspect.isclass(type_def) and issubclass(type_def, BaseModel):
            type_def.__module__ = _DYNAMIC_MODULE_NAME

    return model
