"""Preview bundles (`preview-bundle/v1`) rendered by the running gallery.

Every artifact is a PNG produced by GPUI's own offscreen renderer through the
automation server; nothing is screen-captured or drawn in Python.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from cli_anything.gpui_ui import __version__
from cli_anything.gpui_ui.core.state import summarize
from cli_anything.gpui_ui.utils import preview_bundle
from cli_anything.gpui_ui.utils.gpui_ui_backend import AutomationClient

SOFTWARE = "gpui-ui"
BUNDLE_KIND = "capture"

RECIPES: dict[str, str] = {
    "window": "One PNG of the whole gallery window (role: hero).",
    "elements": "The whole window (hero) plus one cropped PNG per probed element (role: gallery).",
}


def recipes() -> list[dict[str, str]]:
    return [{"recipe": name, "description": text} for name, text in RECIPES.items()]


def _source_fingerprint(state: dict[str, Any]) -> str:
    return preview_bundle.fingerprint_data(state)


def capture(
    client: AutomationClient,
    root_dir: Path,
    recipe: str = "elements",
    force: bool = False,
    source: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Publishes a bundle for the current gallery state, reusing an identical one
    unless `force`."""
    if recipe not in RECIPES:
        raise ValueError(f"unknown recipe `{recipe}`; choose one of: {', '.join(RECIPES)}")
    state = client.call("state")
    prepared = preview_bundle.prepare_bundle(
        software=SOFTWARE,
        recipe=recipe,
        bundle_kind=BUNDLE_KIND,
        source_fingerprint=_source_fingerprint(state),
        harness_version=__version__,
        root_dir=str(root_dir),
        force=force,
    )
    if prepared["cached"]:
        manifest = prepared["manifest"]
        manifest["cached"] = True
        return manifest

    bundle_dir = prepared["bundle_dir"]
    artifacts_dir = prepared["artifacts_dir"]
    artifacts = []

    window_png = os.path.join(artifacts_dir, "window.png")
    shot = client.call("screenshot", path=window_png)
    artifacts.append(
        preview_bundle.artifact_record(
            bundle_dir, window_png, "window", "hero", "image", "Gallery window",
            width=shot["width"], height=shot["height"],
        )
    )
    if recipe == "elements":
        for item in state.get("elements", []):
            element_png = os.path.join(artifacts_dir, f"element-{item['id']}.png")
            shot = client.call("screenshot", path=element_png, id=item["id"])
            artifacts.append(
                preview_bundle.artifact_record(
                    bundle_dir, element_png, f"element-{item['id']}", "gallery", "image",
                    f"{item['kind']} `{item['id']}` ({item['label']})",
                    width=shot["width"], height=shot["height"],
                )
            )

    summary = summarize(state)
    summary["headline"] = (
        f"{summary['element_count']} elements, theme {summary['theme']}, "
        f"{len(artifacts)} image(s)"
    )
    manifest = preview_bundle.finalize_bundle(
        bundle_dir=bundle_dir,
        bundle_id=prepared["bundle_id"],
        bundle_kind=BUNDLE_KIND,
        software=SOFTWARE,
        recipe=recipe,
        source={"kind": "live-app", "fingerprint": _source_fingerprint(state), **(source or {})},
        artifacts=artifacts,
        summary=summary,
        cache_key=prepared["cache_key"],
        generator={"name": "cli-anything-gpui-ui", "version": __version__, "renderer": "gpui render_to_image"},
        context={"state": state},
    )
    manifest["cached"] = False
    return manifest


def latest(root_dir: Path, recipe: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Returns the newest published bundle without rendering a new one."""
    return preview_bundle.find_latest_manifest(SOFTWARE, recipe=recipe, root_dir=str(root_dir))
