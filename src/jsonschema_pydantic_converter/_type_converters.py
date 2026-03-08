"""Type conversion logic for JSON Schema to Pydantic types."""

import math
import warnings
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Tuple, Union

from pydantic import VERSION as _PYDANTIC_VERSION
from pydantic import ConfigDict, Field, create_model

from ._property_renaming import rename_properties
from ._schema_utils import resolve_ref_path
from ._validators import (
    create_const_validator,
    create_empty_enum_validator,
    create_intersection_validator,
    create_not_validator,
)

_pydantic_version_tuple = tuple(int(x) for x in _PYDANTIC_VERSION.split(".")[:2])
if _pydantic_version_tuple < (2, 11):
    warnings.warn(
        "jsonschema-pydantic-converter: pydantic <2.11 does not honour "
        "serialize_by_alias in ConfigDict. Use "
        "instance.model_dump(by_alias=True) to get original JSON property "
        "names in serialized output.",
        stacklevel=2,
    )


class TypeConverter:
    """Converts JSON Schema types to Pydantic types."""

    def __init__(self, namespace: dict[str, Any]):
        """Initialize the type converter.

        Args:
            namespace: Namespace for storing and resolving type definitions.
        """
        self.namespace = namespace
        self.dynamic_type_counter = 0

    def convert(self, prop: dict[str, Any]) -> Any:
        """Convert a JSON Schema property to a Pydantic type.

        Args:
            prop: The JSON Schema property definition.

        Returns:
            A Pydantic type or model.
        """
        # Handle $ref
        if "$ref" in prop:
            return resolve_ref_path(prop["$ref"])

        # Handle allOf
        if "allOf" in prop:
            return create_intersection_validator(
                prop["allOf"], self.convert, self.namespace
            )

        # Handle anyOf
        if "anyOf" in prop:
            unioned_types = tuple(self.convert(sub) for sub in prop["anyOf"])
            return Union[unioned_types]

        # Handle oneOf
        if "oneOf" in prop:
            unioned_types = tuple(self.convert(sub) for sub in prop["oneOf"])
            return Union[unioned_types]

        # Handle not
        if "not" in prop:
            return create_not_validator(prop["not"], self.convert, self.namespace)

        # Handle const
        if "const" in prop:
            return create_const_validator(prop["const"])

        # Handle enum without type
        if "enum" in prop and "type" not in prop:
            return self._convert_enum(prop["enum"], None, prop.get("title"))

        # Handle if-then-else conditionals
        if "if" in prop:
            if "type" not in prop:
                return Any

        # Handle typed schemas
        if "type" in prop:
            return self._convert_typed(prop)

        # Empty schema or constraint-only schema
        if not prop or prop == {}:
            return Any

        # Try to infer type from constraints
        return self._infer_from_constraints(prop)

    def _convert_enum(
        self,
        enum_values: list[Any],
        base_type_name: str | None,
        title: str | None = None,
    ) -> Any:
        """Convert an enum definition to a Pydantic type.

        Args:
            enum_values: The enum values.
            base_type_name: Optional base type name (e.g., "string", "integer").
            title: Optional title for the enum class.

        Returns:
            Either a Literal type or an Enum class.
        """
        from typing import Literal

        # Check if we need to use Literal instead of Enum
        use_literal = False

        if not enum_values:
            return create_empty_enum_validator()
        elif any(isinstance(v, bool) for v in enum_values):
            use_literal = True
        else:
            types = set(type(v) for v in enum_values)
            if len(types) > 1:
                use_literal = True

        if use_literal:
            if enum_values:
                return Literal[tuple(enum_values)]
            return create_empty_enum_validator()

        # Use Enum for homogeneous non-boolean types
        first_val = enum_values[0]
        if isinstance(first_val, str):
            enum_base_type: Any = str
        elif isinstance(first_val, int):
            enum_base_type = int
        elif isinstance(first_val, float):
            enum_base_type = float
        else:
            return Literal[tuple(enum_values)]

        dynamic_members = {f"KEY_{i}": value for i, value in enumerate(enum_values)}

        # Use the title if provided, otherwise use a dynamic name
        enum_name = title if title else "DynamicEnum"

        class DynamicEnum(enum_base_type, Enum):
            pass

        return DynamicEnum(enum_name, dynamic_members)  # type: ignore[call-arg]

    def _convert_typed(self, prop: dict[str, Any]) -> Any:
        """Convert a schema with explicit type field.

        Args:
            prop: The schema with a "type" field.

        Returns:
            The converted Pydantic type.
        """
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": List,
            "object": Dict[str, Any],
            "null": None,
        }

        type_ = prop["type"]

        # Handle enum with type
        if "enum" in prop:
            return self._convert_enum(prop["enum"], type_, prop.get("title"))

        # Handle arrays
        if type_ == "array":
            return self._convert_array(prop)

        # Handle strings with constraints
        if type_ == "string":
            return self._convert_string(prop)

        # Handle numbers with constraints
        if type_ in ("integer", "number"):
            base_type = type_mapping[type_]
            assert isinstance(base_type, type)  # int or float
            return self._convert_number(prop, base_type)

        # Handle objects
        if type_ == "object":
            return self._convert_object(prop)

        if type_ not in type_mapping:
            raise ValueError(f"Unknown JSON Schema type: {type_!r}")

        return type_mapping[type_]

    def _convert_array(self, prop: dict[str, Any]) -> Any:
        """Convert an array schema."""
        items_value = prop.get("items")
        prefix_items = prop.get("prefixItems")

        # Handle tuple validation
        if isinstance(items_value, list) or prefix_items:
            tuple_schemas = prefix_items if prefix_items else items_value
            tuple_types = tuple(self.convert(item) for item in tuple_schemas)  # type: ignore[union-attr]
            return Tuple[tuple_types]

        # Regular array with single item type
        item_type: Any = self.convert(items_value if items_value else {})

        # Handle array constraints
        if "minItems" in prop or "maxItems" in prop or "uniqueItems" in prop:
            constraints = {}
            if "minItems" in prop:
                constraints["min_length"] = prop["minItems"]
            if "maxItems" in prop:
                constraints["max_length"] = prop["maxItems"]

            list_type = List[item_type]
            if constraints or prop.get("uniqueItems"):
                if constraints:
                    return Annotated[list_type, Field(**constraints)]
            return list_type

        return List[item_type]

    def _convert_string(self, prop: dict[str, Any]) -> Any:
        """Convert a string schema with constraints."""
        constraints = {}
        if "minLength" in prop:
            constraints["min_length"] = prop["minLength"]
        if "maxLength" in prop:
            constraints["max_length"] = prop["maxLength"]
        if "pattern" in prop:
            constraints["pattern"] = prop["pattern"]

        if constraints:
            return Annotated[str, Field(**constraints)]
        return str

    def _convert_number(self, prop: dict[str, Any], base_type: type) -> Any:
        """Convert a numeric schema with constraints."""
        constraints = {}

        def floor_if_int(value: Any) -> Any:
            return math.floor(value) if base_type is int else value

        def ceil_if_int(value: Any) -> Any:
            return math.ceil(value) if base_type is int else value

        if "minimum" in prop:
            constraints["ge"] = ceil_if_int(prop["minimum"])
        if "maximum" in prop:
            constraints["le"] = floor_if_int(prop["maximum"])
        if "exclusiveMinimum" in prop:
            constraints["gt"] = floor_if_int(prop["exclusiveMinimum"])
        if "exclusiveMaximum" in prop:
            constraints["lt"] = ceil_if_int(prop["exclusiveMaximum"])
        if "multipleOf" in prop:
            constraints["multiple_of"] = prop["multipleOf"]

        if constraints:
            return Annotated[base_type, Field(**constraints)]
        return base_type

    def _convert_object(self, prop: dict[str, Any]) -> Any:
        """Convert an object schema."""
        if "properties" not in prop:
            # Handle additionalProperties for empty objects
            if "additionalProperties" in prop:
                if prop["additionalProperties"] is False:
                    # Empty object with no additional properties
                    return create_model(
                        f"DynamicType_{self.dynamic_type_counter}",
                        __config__=ConfigDict(extra="forbid", serialize_by_alias=True),
                    )
            return Dict[str, Any]

        # Generate title for the model
        if "title" in prop and prop["title"]:
            title = prop["title"]
        else:
            title = f"DynamicType_{self.dynamic_type_counter}"
            self.dynamic_type_counter += 1

        # Rename reserved / underscore-prefixed property names inline
        raw_required = prop.get("required", [])
        field_map, required_fields = rename_properties(prop["properties"], raw_required)

        # Build fields
        fields: dict[str, Any] = {}
        for original_name, property in prop["properties"].items():
            safe_name, alias = field_map[original_name]
            pydantic_type = (
                self.convert(property) if isinstance(property, dict) else Any
            )
            field_kwargs: dict[str, Any] = {}

            if isinstance(property, dict) and "default" in property:
                field_kwargs["default"] = property["default"]
            elif safe_name not in required_fields:
                pydantic_type = Optional[pydantic_type]
                field_kwargs["default"] = None

            if isinstance(property, dict):
                if "description" in property:
                    field_kwargs["description"] = property["description"]
                if "title" in property:
                    field_kwargs["title"] = property["title"]

            field_kwargs["alias"] = alias

            fields[safe_name] = (pydantic_type, Field(**field_kwargs))

        # Build ConfigDict
        config = ConfigDict(serialize_by_alias=True)

        if "additionalProperties" in prop:
            if prop["additionalProperties"] is False:
                config["extra"] = "forbid"
            elif prop["additionalProperties"] is True:
                config["extra"] = "allow"
        else:
            # Default is to allow additional properties
            config["extra"] = "allow"

        object_model = create_model(title, __config__=config, **fields)

        if "description" in prop:
            object_model.__doc__ = prop["description"]

        return object_model

    def _infer_from_constraints(self, prop: dict[str, Any]) -> Any:
        """Try to infer type from constraint keywords."""
        # Numeric constraints
        if any(
            k in prop
            for k in [
                "minimum",
                "maximum",
                "exclusiveMinimum",
                "exclusiveMaximum",
                "multipleOf",
            ]
        ):
            return self._convert_number(prop, float)

        # String constraints
        if any(k in prop for k in ["minLength", "maxLength", "pattern"]):
            return self._convert_string(prop)

        # Array constraints
        if any(k in prop for k in ["minItems", "maxItems", "uniqueItems"]):
            return self._convert_array(prop)

        return Any
