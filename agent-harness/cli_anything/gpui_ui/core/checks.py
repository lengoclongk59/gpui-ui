"""Assertions over gallery state, for automated component tests.

Each check returns a result dict `{"passed": bool, "check": .., "failures": [..]}`
so the CLI can print it and exit non-zero when it fails.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from cli_anything.gpui_ui.core.state import find_element


def _result(check: str, failures: list[str], **context: Any) -> dict[str, Any]:
    return {"passed": not failures, "check": check, "failures": failures, **context}


def check_element(
    state: dict[str, Any],
    element_id: str,
    *,
    kind: Optional[str] = None,
    label: Optional[str] = None,
    disabled: Optional[bool] = None,
    checked: Optional[bool] = None,
) -> dict[str, Any]:
    """Compares one element against the expected values that are not None."""
    item = find_element(state, element_id)
    failures = []
    expectations = {"kind": kind, "label": label, "disabled": disabled, "checked": checked}
    for key, expected in expectations.items():
        if expected is None:
            continue
        actual = item.get(key)
        if actual != expected:
            failures.append(f"{element_id}.{key}: expected {expected!r}, got {actual!r}")
    return _result(f"element {element_id}", failures, element=item)


def parse_expected(value: str) -> Any:
    """Parses a command-line value as JSON, falling back to the raw string.

    `3` -> 3, `true` -> True, `"on"` -> "on", `on` -> "on".
    """
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def check_gallery(state: dict[str, Any], key: str, expected: Any) -> dict[str, Any]:
    """Compares one value the gallery owns (`clicks`, `notifications`, ...)."""
    gallery = state.get("gallery", {})
    if key not in gallery:
        known = ", ".join(sorted(gallery)) or "none"
        return _result(f"gallery {key}", [f"gallery has no `{key}`; known keys: {known}"])
    actual = gallery[key]
    failures = [] if actual == expected else [f"gallery.{key}: expected {expected!r}, got {actual!r}"]
    return _result(f"gallery {key}", failures, actual=actual, expected=expected)


def check_theme(state: dict[str, Any], expected: str) -> dict[str, Any]:
    actual = state.get("theme")
    failures = [] if actual == expected else [f"theme: expected {expected!r}, got {actual!r}"]
    return _result("theme", failures, actual=actual, expected=expected)
