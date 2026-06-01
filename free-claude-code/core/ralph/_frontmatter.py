"""Minimal YAML-frontmatter serializer/deserializer.

Replaces PyYAML for the limited subset of YAML that Ralph task files need:
scalars (str, int, bool), lists of strings, and nested dicts. This avoids
an external dependency for a format that is simple and well-bounded.

Supported types:
  - str, int, bool
  - list[str]
  - dict[str, str | int | bool | list[str]]

Unsupported: nested lists, dict values beyond the above, flow-style YAML,
YAML tags, anchors, aliases, timestamps, floats.
"""

from __future__ import annotations

from typing import Any


class FrontmatterError(Exception):
    """Raised when frontmatter formatting is invalid."""


def dumps(data: dict[str, Any]) -> str:
    """Serialize a dict to a YAML-frontmatter string.

    Produces output compatible with ``safe_load`` in this module.
    """
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"- {_repr_scalar(item)}" for item in value)
        elif isinstance(value, dict):
            if not value:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                for k, v in value.items():
                    lines.append(f"  {k}: {_repr_scalar(v)}")
        else:
            lines.append(f"{key}: {_repr_scalar(value)}")
    return "\n".join(lines) + "\n"


def _repr_scalar(value: Any) -> str:
    """Format a scalar value for YAML output."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _quote_if_needed(value)
    return str(value)


def _quote_if_needed(value: str) -> str:
    """Quote a string if it contains characters ambiguous in YAML."""
    if not value:
        return '""'
    # Only quote when necessary to avoid YAML ambiguity
    if value[0] in ("'", '"') or value[-1] in ("'", '"'):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if value.startswith("*") or ":" in value or "#" in value:
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return value


def safe_load(text: str) -> dict[str, Any]:
    """Parse a YAML-frontmatter string into a dict.

    Supports the subset produced by ``dumps``: top-level keys with
    scalar values, indented list items, and indented nested dicts.
    """
    if not text.strip():
        return {}

    result: dict[str, Any] = {}
    lines = text.split("\n")
    current_key: str | None = None
    current_list: list[Any] | None = None
    current_dict: dict[str, Any] | None = None

    for line in lines:
        stripped = line.rstrip()

        # Skip empty lines
        if not stripped.strip():
            continue

        # Check if this is a continuation of a nested dict
        if current_dict is not None and stripped.startswith("  ") and ":" in stripped:
            k, _, v = stripped.strip().partition(":")
            v = v.strip()
            current_dict[k.strip()] = _parse_scalar(v)
            continue

        # Check if this is a list item (indented with "- ")
        if stripped.lstrip().startswith("- "):
            item_text = stripped.lstrip()[2:].strip()
            if current_list is not None:
                current_list.append(_parse_scalar(item_text))
            continue

        # Top-level key: value
        if ":" not in stripped:
            raise FrontmatterError(f"Expected key:value pair, got: {stripped!r}")

        # Flush previous list/dict if any (only non-empty -- preserve
        # the "" placeholder for empty values like ``key:``)
        if current_key is not None:
            if current_list is not None and current_list:
                result[current_key] = current_list
            elif current_dict is not None and current_dict:
                result[current_key] = current_dict

        current_key, _, raw_value = stripped.partition(":")
        current_key = current_key.strip()
        raw_value = raw_value.strip()

        # Empty value might be a list or dict start
        if not raw_value:
            # Peek ahead - look at the indent of the next line
            current_list = None
            current_dict = None
            # Actually, if raw_value is empty, it could be a list or dict
            # We set a marker and let subsequent lines fill it
            # But we need to know if it's a list or dict
            # For safety, we'll set it as empty and overwrite if filled
            result[current_key] = ""
            current_list = []
            current_dict = {}
            continue

        if raw_value == "[]":
            result[current_key] = []
            current_list = None
            current_dict = None
        elif raw_value == "{}":
            result[current_key] = {}
            current_list = None
            current_dict = None
        else:
            result[current_key] = _parse_scalar(raw_value)
            current_list = None
            current_dict = None

    # Flush last list/dict
    if current_key is not None:
        if current_list is not None and current_list:
            result[current_key] = current_list
        elif current_dict is not None and current_dict:
            result[current_key] = current_dict

    return result


def _parse_scalar(value: str) -> Any:
    """Parse a YAML scalar string into a Python value."""
    if not value:
        return ""
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    # Remove surrounding quotes
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        inner = value[1:-1]
        if value[0] == "'":
            inner = inner.replace("''", "'")
        return inner
    return value
