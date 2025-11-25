"""Convert JSON Schema definitions to Pydantic TypeAdapters with dynamically generated models.

This module provides functionality to transform JSON Schema dictionaries into Pydantic v2
models at runtime, wrapped in TypeAdapters for validation and serialization.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import BeforeValidator, Field, TypeAdapter, ValidationError, create_model


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
                and schema composition (allOf, anyOf).

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

    dynamic_type_counter = 0
    namespace: dict[str, Any] = {}

    def _create_intersection_type(sub_schemas: list[dict[str, Any]]) -> Any:
        """Create an Intersection type that validates against all sub-schemas."""
        converted_types = [convert_type(sub) for sub in sub_schemas]

        def validate_all(value: Any) -> Any:
            """Validate that the value satisfies all sub-schemas."""
            for converted_type in converted_types:
                try:
                    adapter = TypeAdapter(converted_type)
                    adapter.rebuild(force=True, _types_namespace=namespace)
                    adapter.validate_python(value)
                except Exception as e:
                    raise ValueError(
                        f"Value does not satisfy all schemas in allOf: {e}"
                    ) from e
            return value

        # Check if any sub-schema contains $ref - if so, we can't preserve the structure
        # in json_schema_extra because Pydantic can't resolve the refs
        has_refs = any("$ref" in sub for sub in sub_schemas)

        if has_refs:
            # Don't override json_schema when $refs are present
            return Annotated[
                Any,
                BeforeValidator(validate_all),
            ]
        else:

            def json_schema_extra(schema_dict: dict[str, Any]) -> None:
                """Override the generated schema with the original allOf structure."""
                schema_dict.clear()
                schema_dict["allOf"] = sub_schemas

            return Annotated[
                Any,
                BeforeValidator(validate_all),
                Field(json_schema_extra=json_schema_extra),
            ]

    def _create_not_type(not_schema: dict[str, Any]) -> Any:
        """Create a type that validates against NOT matching a schema."""
        converted_type = convert_type(not_schema)

        def validate_not(value: Any) -> Any:
            """Validate that the value does NOT satisfy the schema."""
            try:
                adapter = TypeAdapter(converted_type)
                adapter.rebuild(force=True, _types_namespace=namespace)
                adapter.validate_python(value)
                # If validation succeeded, it means the value matches - should fail
                raise ValueError(
                    "Value should not satisfy the 'not' schema but it does"
                )
            except ValidationError:
                # Validation failed, which is what we want for 'not'
                return value
            except ValueError as e:
                # Re-raise our custom error
                if "should not satisfy" in str(e):
                    raise
                # Other ValueError means validation failed, which is good
                return value

        def json_schema_extra(schema_dict: dict[str, Any]) -> None:
            """Override the generated schema with the original not structure."""
            schema_dict.clear()
            schema_dict["not"] = not_schema

        return Annotated[
            Any,
            BeforeValidator(validate_not),
            Field(json_schema_extra=json_schema_extra),
        ]

    def _create_const_type(const_value: Any) -> Any:
        """Create a type that validates against an exact constant value."""

        def validate_const(value: Any) -> Any:
            """Validate that the value equals the const value."""
            if value != const_value:
                raise ValueError(
                    f"Value must be exactly {const_value!r}, got {value!r}"
                )
            return value

        def json_schema_extra(schema_dict: dict[str, Any]) -> None:
            """Override the generated schema with the original const structure."""
            schema_dict.clear()
            schema_dict["const"] = const_value

        return Annotated[
            Any,
            BeforeValidator(validate_const),
            Field(json_schema_extra=json_schema_extra),
        ]

    def convert_type(prop: dict[str, Any]) -> Any:
        nonlocal dynamic_type_counter

        if "$ref" in prop:
            # Handle $ref with nested paths like #/$defs/Address/$defs/Country
            ref = prop["$ref"]
            if ref.startswith("#/"):
                # Remove leading #/ and split by /
                ref_path = ref[2:]
                # Extract the actual path (skip $defs/definitions keywords)
                parts = ref_path.split("/")
                # Filter out $defs and definitions, keep the actual definition names
                name_parts = [p for p in parts if p not in ("$defs", "definitions")]
                # Join with underscore and capitalize
                full_name = "_".join(name_parts).capitalize()
                return full_name
            else:
                # External ref - just use the last part
                return ref.split("/")[-1].capitalize()

        if "allOf" in prop:
            return _create_intersection_type(prop["allOf"])

        if "anyOf" in prop:
            unioned_types = tuple(convert_type(sub) for sub in prop["anyOf"])
            return Union[unioned_types]

        if "oneOf" in prop:
            # oneOf is like anyOf/Union - validates if exactly one matches
            # For type conversion, we treat it as Union (constraint not enforced)
            unioned_types = tuple(convert_type(sub) for sub in prop["oneOf"])
            return Union[unioned_types]

        if "not" in prop:
            return _create_not_type(prop["not"])

        # Handle const keyword - exact value matching
        if "const" in prop:
            return _create_const_type(prop["const"])

        # Handle enum without type
        if "enum" in prop and "type" not in prop:
            # Create enum from values
            enum_values = prop["enum"]

            # Check if we need to use Literal instead of Enum
            # Booleans can't be Enum bases (metaclass conflict)
            # Mixed types also can't be Enum bases
            # Empty enums should use an empty Literal
            use_literal = False

            if not enum_values:
                # Empty enum - use empty Literal which rejects everything
                use_literal = True
            elif any(isinstance(v, bool) for v in enum_values):
                # Has booleans - must use Literal
                use_literal = True
            else:
                # Check if all values are same type
                types = set(type(v) for v in enum_values)
                if len(types) > 1:
                    # Mixed types - use Literal
                    use_literal = True

            if use_literal:
                from typing import Literal

                if enum_values:
                    return Literal[tuple(enum_values)]
                else:
                    # Empty enum - use BeforeValidator that always rejects
                    # Can't use empty Literal as Pydantic doesn't support it
                    def reject_all(v: Any) -> Any:
                        raise ValueError("No values are allowed for empty enum")

                    return Annotated[Any, BeforeValidator(reject_all)]

            # Use Enum for homogeneous non-boolean types
            first_val = enum_values[0]
            if isinstance(first_val, str):
                enum_base_type: Any = str
            elif isinstance(first_val, int):
                enum_base_type = int
            elif isinstance(first_val, float):
                enum_base_type = float
            else:
                # Fallback to Literal for other types
                from typing import Literal

                return Literal[tuple(enum_values)]

            dynamic_members = {f"KEY_{i}": value for i, value in enumerate(enum_values)}

            class DynamicEnumNoType(enum_base_type, Enum):
                pass

            return DynamicEnumNoType(prop.get("title", "DynamicEnum"), dynamic_members)  # type: ignore[call-arg]

        # Handle if-then-else conditionals
        # These are complex conditionals that are hard to enforce at type level
        # We just convert the base type if present, or return Any
        if "if" in prop:
            # If there's a type in the root, use that, otherwise Any
            if "type" in prop:
                pass  # Will be handled below
            else:
                return Any

        if "type" in prop:
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

            if "enum" in prop:
                enum_base_type_with_type: Any = type_mapping.get(type_, Any)
                dynamic_members = {
                    f"KEY_{i}": value for i, value in enumerate(prop["enum"])
                }

                class DynamicEnumWithType(enum_base_type_with_type, Enum):
                    pass

                return DynamicEnumWithType(
                    prop.get("title", "DynamicEnum"), dynamic_members
                )  # type: ignore[call-arg]

            if type_ == "array":
                # Handle tuple validation (items as array) or prefixItems
                items_value = prop.get("items")
                prefix_items = prop.get("prefixItems")

                if isinstance(items_value, list) or prefix_items:
                    # Tuple validation: items is an array of schemas
                    from typing import Tuple

                    tuple_schemas = prefix_items if prefix_items else items_value
                    # mypy: tuple_schemas is guaranteed to be a list here due to the if condition
                    tuple_types = tuple(convert_type(item) for item in tuple_schemas)  # type: ignore[union-attr]
                    return Tuple[tuple_types]

                # Regular array with single item type
                item_type: Any = convert_type(items_value if items_value else {})

                # Handle array constraints if present
                if "minItems" in prop or "maxItems" in prop or "uniqueItems" in prop:
                    constraints = {}
                    if "minItems" in prop:
                        constraints["min_length"] = prop["minItems"]
                    if "maxItems" in prop:
                        constraints["max_length"] = prop["maxItems"]

                    list_type = List[item_type]
                    if constraints or prop.get("uniqueItems"):
                        # For uniqueItems, we'd need a custom validator
                        # For now, just apply min/max_length constraints
                        if constraints:
                            return Annotated[list_type, Field(**constraints)]
                    return list_type

                return List[item_type]

            # Handle string constraints
            if type_ == "string":
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

            # Handle numeric constraints
            if type_ in ("integer", "number"):
                base_type = type_mapping[type_]
                constraints = {}

                if "minimum" in prop:
                    constraints["ge"] = prop["minimum"]
                if "maximum" in prop:
                    constraints["le"] = prop["maximum"]
                if "exclusiveMinimum" in prop:
                    constraints["gt"] = prop["exclusiveMinimum"]
                if "exclusiveMaximum" in prop:
                    constraints["lt"] = prop["exclusiveMaximum"]
                if "multipleOf" in prop:
                    constraints["multiple_of"] = prop["multipleOf"]

                if constraints:
                    return Annotated[base_type, Field(**constraints)]
                return base_type

            if type_ == "object":
                if "properties" not in prop:
                    return Dict[str, Any]

                # Generate title for the model
                if "title" in prop and prop["title"]:
                    title = prop["title"]
                else:
                    title = f"DynamicType_{dynamic_type_counter}"
                    dynamic_type_counter += 1

                # Build fields
                fields: dict[str, Any] = {}
                required_fields = prop.get("required", [])

                for name, property in prop["properties"].items():
                    pydantic_type = convert_type(property)
                    field_kwargs = {}

                    if "default" in property:
                        field_kwargs["default"] = property["default"]
                    elif name not in required_fields:
                        pydantic_type = Optional[pydantic_type]
                        field_kwargs["default"] = None

                    if "description" in property:
                        field_kwargs["description"] = property["description"]
                    if "title" in property:
                        field_kwargs["title"] = property["title"]

                    fields[name] = (pydantic_type, Field(**field_kwargs))

                object_model = create_model(title, **fields)
                if "description" in prop:
                    object_model.__doc__ = prop["description"]
                return object_model

            return type_mapping.get(type_, Any)

        if not prop or prop == {}:
            return Any

        # If we reach here, it might be a schema with only constraints (no type)
        # For example: {"minimum": 0, "maximum": 100}
        # Try to infer type from constraints
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
            # Numeric constraints - default to number
            base_type = float
            constraints = {}
            if "minimum" in prop:
                constraints["ge"] = prop["minimum"]
            if "maximum" in prop:
                constraints["le"] = prop["maximum"]
            if "exclusiveMinimum" in prop:
                constraints["gt"] = prop["exclusiveMinimum"]
            if "exclusiveMaximum" in prop:
                constraints["lt"] = prop["exclusiveMaximum"]
            if "multipleOf" in prop:
                constraints["multiple_of"] = prop["multipleOf"]

            if constraints:
                return Annotated[base_type, Field(**constraints)]
            return base_type

        if any(k in prop for k in ["minLength", "maxLength", "pattern"]):
            # String constraints
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

        if any(k in prop for k in ["minItems", "maxItems", "uniqueItems"]):
            # Array constraints - but we need items type, so just return List[Any]
            constraints = {}
            if "minItems" in prop:
                constraints["min_length"] = prop["minItems"]
            if "maxItems" in prop:
                constraints["max_length"] = prop["maxItems"]

            if constraints:
                return Annotated[List[Any], Field(**constraints)]
            return List[Any]

        if any(
            k in prop
            for k in [
                "minProperties",
                "maxProperties",
                "properties",
                "required",
                "additionalProperties",
                "patternProperties",
                "propertyNames",
            ]
        ):
            # Object constraints - return Dict[str, Any]
            return Dict[str, Any]

        raise ValueError(f"Unsupported schema: {prop}")

    # Recursively collect all definitions (including nested ones)
    def collect_definitions(
        schema_dict: dict[str, Any], path: str = ""
    ) -> dict[str, dict[str, Any]]:
        """Recursively collect all $defs/$definitions from schema."""
        defs: dict[str, dict[str, Any]] = {}

        # Get definitions at current level
        current_defs = schema_dict.get("$defs", schema_dict.get("definitions", {}))

        for name, definition in current_defs.items():
            # Build full path for nested definitions
            full_name = f"{path}/{name}" if path else name
            defs[full_name] = definition

            # Recursively collect nested definitions
            if isinstance(definition, dict):
                nested_defs = collect_definitions(definition, full_name)
                defs.update(nested_defs)

        return defs

    # Collect all definitions (top-level and nested)
    all_definitions = collect_definitions(schema)

    # Populate namespace with all definitions
    for name, definition in all_definitions.items():
        model = convert_type(definition)
        # Use the full path as the key, but capitalize for consistency
        namespace[name.replace("/", "_").capitalize()] = model

    # Convert the main schema
    model = convert_type(schema)
    type_adapter = TypeAdapter(model)
    type_adapter.rebuild(force=True, _types_namespace=namespace)
    return type_adapter
