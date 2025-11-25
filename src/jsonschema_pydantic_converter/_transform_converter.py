"""Type converter specifically for the deprecated transform() function.

This converter extends TypeConverter to handle allOf by merging schemas into BaseModels
instead of using validators, which is the behavior expected by transform().
"""

from typing import Any

from ._schema_utils import (
    is_allof_object_schemas,
    merge_allof_constraint_schemas,
    merge_allof_object_schemas,
)
from ._type_converters import TypeConverter


class TransformConverter(TypeConverter):
    """Type converter that merges allOf schemas into BaseModels for transform()."""

    def __init__(self, namespace: dict[str, Any]):
        """Initialize the transform converter.

        Args:
            namespace: Namespace for storing and resolving type definitions.
        """
        super().__init__(namespace)
        self.combined_model_counter = 0

    def convert(self, prop: dict[str, Any]) -> Any:
        """Convert a JSON Schema property to a Pydantic type.

        This override handles allOf differently than the parent class,
        merging object schemas into a single BaseModel instead of using validators.

        Args:
            prop: The JSON Schema property definition.

        Returns:
            A Pydantic type or model.
        """
        # Handle allOf specially for transform() - merge into BaseModel
        if "allOf" in prop:
            allof_schemas = prop["allOf"]

            # Check if we're dealing with object schemas
            if is_allof_object_schemas(allof_schemas):
                # Determine title for the merged model
                if "title" in prop:
                    title = prop["title"]
                else:
                    title = f"CombinedModel_{self.combined_model_counter}"
                    self.combined_model_counter += 1

                # Merge the object schemas
                merged_schema = merge_allof_object_schemas(allof_schemas, title)

                # Convert the merged schema to a model
                return self.convert(merged_schema)
            else:
                # Merge constraint schemas
                merged_schema = merge_allof_constraint_schemas(allof_schemas)

                # Convert the merged non-object schema
                return self.convert(merged_schema)

        # For all other cases, use the parent class implementation
        return super().convert(prop)
