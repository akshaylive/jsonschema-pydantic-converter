"""anonymous models containing a $ref must be rebuilt."""

import copy

from pydantic import BaseModel, create_model

from jsonschema_pydantic_converter import transform


def _nested(model, field):
    """The BaseModel inside Optional[...] on `field`."""
    ann = model.__pydantic_fields__[field].annotation
    return next(
        a for a in ann.__args__ if isinstance(a, type) and issubclass(a, BaseModel)
    )


def _clone(model):
    """What LangChain does in _create_subset_model_v2: copy raw annotations
    into a create_model in a DIFFERENT module."""
    clone = create_model(
        model.__name__,
        **{n: (f.annotation, f) for n, f in model.__pydantic_fields__.items()},
    )
    clone.model_json_schema()  # forces the core schema to be built
    return clone


# An inline ("anonymous") object whose own property is a $ref.
SCHEMA = {
    "title": "Create_Issue",
    "type": "object",
    "properties": {
        "fields": {  # anonymous: not under $defs
            "type": "object",
            "properties": {
                "project": {"$ref": "#/$defs/Project"},
                "summary": {"type": "string"},
            },
        },
    },
    "$defs": {
        "Project": {"type": "object", "properties": {"key": {"type": "string"}}},
    },
}


def test_anonymous_model_with_ref_is_complete():
    model = transform(SCHEMA)
    assert model.__pydantic_complete__
    # the regression: the nested anonymous model was left holding ForwardRef('__Project')
    assert _nested(model, "fields").__pydantic_complete__

    # does not raise: cloning copies raw annotations into another module,
    # which fails if any nested model still holds an unresolved ForwardRef
    _clone(model)


def test_anonymous_model_with_ref_is_complete_after_json_schema_roundtrip():
    """model -> JSON Schema -> inline a $ref -> model."""
    first = transform(SCHEMA)
    rt = first.model_json_schema()

    # pydantic hoisted the anonymous object into $defs under its class name
    assert "DynamicType_1" in rt["$defs"]

    # navigating to a nested path inlines a deepcopy of the $def; properties off
    # the navigated path keep their $ref
    holder = rt["properties"]["fields"]["anyOf"]
    holder[0] = copy.deepcopy(rt["$defs"][holder[0]["$ref"].rsplit("/", 1)[1]])
    assert holder[0]["properties"]["project"]["anyOf"][0] == {
        "$ref": "#/$defs/DynamicType_0"
    }

    second = transform(rt)
    assert second.__pydantic_complete__
    assert _nested(second, "fields").__pydantic_complete__

    # does not raise: cloning copies raw annotations into another module,
    # which fails if any nested model still holds an unresolved ForwardRef
    _clone(second)


def test_anonymous_model_nested_inside_a_def_is_complete():
    schema = {
        "title": "Root",
        "type": "object",
        "properties": {"outer": {"$ref": "#/$defs/Outer"}},
        "$defs": {
            "Outer": {
                "type": "object",
                "properties": {
                    "inline": {
                        "type": "object",  # anonymous, inside a $def
                        "properties": {"p": {"$ref": "#/$defs/Leaf"}},
                    }
                },
            },
            "Leaf": {"type": "object", "properties": {"k": {"type": "string"}}},
        },
    }
    model = transform(schema)
    inline = _nested(_nested(model, "outer"), "inline")
    assert inline.__pydantic_complete__
