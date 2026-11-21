"""Pure helpers over the state object returned by the gallery."""

from __future__ import annotations

from typing import Any, Optional


class ElementNotFound(LookupError):
    """No element with the requested test id."""


def elements(state: dict[str, Any], kind: Optional[str] = None) -> list[dict[str, Any]]:
    """Returns the elements of `state`, optionally only those of `kind`."""
    items = list(state.get("elements", []))
    if kind:
        items = [item for item in items if item.get("kind") == kind]
    return items


def element_ids(state: dict[str, Any]) -> list[str]:
    return [item["id"] for item in state.get("elements", [])]


def find_element(state: dict[str, Any], element_id: str) -> dict[str, Any]:
    for item in state.get("elements", []):
        if item.get("id") == element_id:
            return item
    known = ", ".join(element_ids(state)) or "none"
    raise ElementNotFound(f"no element with id `{element_id}`; known ids: {known}")


def summarize(state: dict[str, Any]) -> dict[str, Any]:
    """A compact view for status lines: theme, gallery values, element count."""
    kinds: dict[str, int] = {}
    for item in state.get("elements", []):
        kinds[item.get("kind", "?")] = kinds.get(item.get("kind", "?"), 0) + 1
    return {
        "theme": state.get("theme"),
        "gallery": state.get("gallery", {}),
        "element_count": len(state.get("elements", [])),
        "kinds": kinds,
    }


def element_row(item: dict[str, Any]) -> list[str]:
    """Formats one element as a table row."""
    bounds = item.get("bounds") or {}
    checked = item.get("checked")
    return [
        item.get("id", ""),
        item.get("kind", ""),
        str(item.get("label", "")),
        "yes" if item.get("disabled") else "no",
        "-" if checked is None else ("on" if checked else "off"),
        f"{bounds.get('x', 0):.0f},{bounds.get('y', 0):.0f} "
        f"{bounds.get('width', 0):.0f}x{bounds.get('height', 0):.0f}",
    ]


ELEMENT_HEADERS = ["id", "kind", "label", "disabled", "checked", "bounds"]
