"""Property name sanitization for reserved and underscore-prefixed names.

Helpers to detect JSON Schema property names that would conflict with Pydantic
BaseModel attributes or be treated as private fields (underscore-prefixed), and
to compute safe replacement names.
"""

from typing import Any

from pydantic import BaseModel

# Computed once at import time; stays future-proof across Pydantic versions.
_RESERVED_NAMES: frozenset[str] = frozenset(
    name for name in dir(BaseModel) if not name.startswith("__")
)


def needs_rename(name: str) -> bool:
    """Return True if a property name must be renamed."""
    return name.startswith("_") or name in _RESERVED_NAMES


def compute_safe_name(original: str, taken: set[str]) -> str:
    """Derive a safe Pydantic field name from *original*.

    - Strips leading underscores.
    - Falls back to ``"field"`` if stripping yields an empty string.
    - Appends ``_`` until the name is neither reserved nor already taken.
    """
    name = original.lstrip("_") or "field"
    while name in _RESERVED_NAMES or name in taken:
        name += "_"
    return name


def rename_properties(
    properties: dict[str, Any],
    required_fields: list[str],
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Compute renames for a properties dict.

    Args:
        properties: The JSON Schema ``properties`` mapping.
        required_fields: The ``required`` array from the schema.

    Returns:
        A tuple of:
        - field_map: ``{original_name: (safe_name, alias)}`` for every
          property.  ``alias`` is always set to the original name (for
          consistency across all fields).
        - updated_required: the required list with renamed entries swapped.
    """
    to_rename = {name for name in properties if needs_rename(name)}

    if not to_rename:
        result: dict[str, tuple[str, str]] = {name: (name, name) for name in properties}
        return result, required_fields

    taken: set[str] = {name for name in properties if name not in to_rename}

    renames: dict[str, str] = {}
    for original in properties:
        if original in to_rename:
            new = compute_safe_name(original, taken)
            renames[original] = new
            taken.add(new)

    field_map: dict[str, tuple[str, str]] = {}
    for name in properties:
        if name in renames:
            field_map[name] = (renames[name], name)
        else:
            field_map[name] = (name, name)

    updated_required = [renames.get(r, r) for r in required_fields]
    return field_map, updated_required
