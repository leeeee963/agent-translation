"""Shared key-path utilities for JSON/YAML/XML parsers.

Functions
---------
get_by_path(obj, path)        -- navigate a nested dict/list by dot-path
set_by_path(obj, path, value) -- mutate in place
iter_leaf_strings(obj, path)  -- yield (dot_path, value) for all string leaves
"""
from __future__ import annotations

from typing import Any, Generator


def get_by_path(obj: Any, path: str) -> Any:
    """Navigate *obj* by *path* (dot-separated keys/indices).

    Example::

        get_by_path({"a": {"b": "v"}}, "a.b")  # -> "v"
        get_by_path({"a": [1, 2]}, "a.1")       # -> 2
    """
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj[part]
        elif isinstance(obj, list):
            obj = obj[int(part)]
        else:
            raise KeyError(f"Cannot navigate into {type(obj)} with key '{part}'")
    return obj


def set_by_path(obj: Any, path: str, value: Any) -> None:
    """Set *value* at *path* inside *obj*, mutating it in place."""
    parts = path.split(".")
    for part in parts[:-1]:
        if isinstance(obj, dict):
            obj = obj[part]
        elif isinstance(obj, list):
            obj = obj[int(part)]
        else:
            raise KeyError(f"Cannot navigate into {type(obj)} with key '{part}'")
    last = parts[-1]
    if isinstance(obj, dict):
        obj[last] = value
    elif isinstance(obj, list):
        obj[int(last)] = value
    else:
        raise KeyError(f"Cannot set key '{last}' on {type(obj)}")


def iter_leaf_strings(
    obj: Any,
    prefix: str = "",
    skip_keys: set[str] | None = None,
) -> Generator[tuple[str, str], None, None]:
    """Recursively yield *(dot_path, value)* for all string leaf nodes.

    Parameters
    ----------
    obj:
        A nested dict / list / scalar parsed from JSON or YAML.
    prefix:
        Current dot-path prefix (used in recursion).
    skip_keys:
        Set of key names whose values should NOT be yielded (e.g. "url", "id").
    """
    skip_keys = skip_keys or set()

    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if k in skip_keys:
                continue
            yield from iter_leaf_strings(v, full_key, skip_keys)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            full_key = f"{prefix}.{i}" if prefix else str(i)
            yield from iter_leaf_strings(v, full_key, skip_keys)
    elif isinstance(obj, str) and obj.strip():
        yield prefix, obj
