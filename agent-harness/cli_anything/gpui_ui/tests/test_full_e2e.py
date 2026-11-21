"""End-to-end tests against the real `story` gallery (GPUI, real window).

`story` must be built (`cli-anything-gpui-ui app build` or `cargo build -p
story`). These tests fail, not skip, when it is missing. Artifact paths are
printed for manual inspection (run with `-s`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cli_anything.gpui_ui.core import png
from cli_anything.gpui_ui.core import preview
from cli_anything.gpui_ui.core import state as state_mod
from cli_anything.gpui_ui.core.session import AppSession, SessionStore
from cli_anything.gpui_ui.utils import gpui_ui_backend as backend

HARNESS_ROOT = Path(__file__).resolve().parents[3]
ALL_IDS = [
    "danger", "disabled", "ghost", "large", "medium", "notifications", "outline",
    "primary", "secondary", "small", "switch-disabled", "toggle-theme",
]


def _resolve_cli(name: str) -> list[str]:
    """Resolve the installed CLI command; falls back to `python -m` for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: uv tool install --editable agent-harness")
    module = "cli_anything." + name.removeprefix("cli-anything-").replace("-", "_")
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    """Starts the real gallery for one test module and stops it afterwards."""
    root = tmp_path_factory.mktemp("story")
    store = SessionStore(root / "session.json")
    started = backend.start_story(backend.find_story(), store.log_path)
    store.save(AppSession(pid=started["pid"], port=started["port"], exe=started["exe"], log=started["log"]))
    client = backend.AutomationClient(started["port"])
    print(f"\n  story: {started['exe']} pid {started['pid']} port {started['port']}")
    yield client, root
    try:
        client.call("quit")
    except backend.BackendError:
        pass
    if backend.pid_alive(started["pid"]):
        backend.kill_process(started["pid"])


@pytest.fixture
def client(app):
    """The app client, reset to a known state (light theme, notifications on)."""
    client, _ = app
    client.call("set_theme", mode="light")
    if not client.call("state")["gallery"]["notifications"]:
        client.call("click", id="notifications")
    return client


@pytest.fixture
def out_dir(app):
    _, root = app
    path = root / "artifacts"
    path.mkdir(exist_ok=True)
    return path


# ── Backend protocol ──────────────────────────────────────────────────


class TestProtocol:
    def test_ping(self, client):
        info = client.call("ping")
        assert info["app"] == "gpui-ui-story" and info["protocol"] == 1

    def test_initial_state_lists_every_component(self, client):
        state = client.call("state")
        assert state_mod.element_ids(state) == ALL_IDS
        for item in state["elements"]:
            bounds = item["bounds"]
            assert bounds["width"] > 0 and bounds["height"] > 0, item
            assert 0 <= bounds["x"] < 960 and 0 <= bounds["y"] < 680, item

    def test_unknown_id_lists_known_ids(self, client):
        with pytest.raises(backend.AutomationError, match="known ids: danger, disabled"):
            client.call("click", id="nope")


# ── Behavior ──────────────────────────────────────────────────────────


class TestBehavior:
    def test_primary_counts_clicks(self, client):
        before = client.call("state")["gallery"]["clicks"]
        for _ in range(3):
            state = client.call("click", id="primary")
        assert state["gallery"]["clicks"] == before + 3

    def test_disabled_button_ignores_clicks(self, client):
        before = client.call("state")["gallery"]["clicks"]
        state = client.call("click", id="disabled")
        assert state["gallery"]["clicks"] == before

    def test_switch_toggles_and_reports_checked(self, client):
        state = client.call("click", id="notifications")
        assert state["gallery"]["notifications"] is False
        assert state_mod.find_element(state, "notifications")["checked"] is False
        state = client.call("click", id="notifications")
        assert state_mod.find_element(state, "notifications")["checked"] is True

    def test_disabled_switch_stays_on(self, client):
        state = client.call("click", id="switch-disabled")
        assert state_mod.find_element(state, "switch-disabled")["checked"] is True

    def test_theme_switch_updates_toggle_label(self, client):
        state = client.call("set_theme", mode="dark")
        assert state["theme"] == "dark"
        assert state_mod.find_element(state, "toggle-theme")["label"] == "Light mode"
        state = client.call("click", id="toggle-theme")
        assert state["theme"] == "light"


# ── Rendering: real PNG output ────────────────────────────────────────


class TestRendering:
    def test_window_screenshot(self, client, out_dir):
        path = out_dir / "window.png"
        result = client.call("screenshot", path=str(path))
        assert png.size(path) == (result["width"], result["height"])
        assert result["width"] >= 900 and result["height"] >= 600
        print(f"\n  PNG: {path} ({path.stat().st_size:,} bytes)")

    def test_primary_crop_is_blue(self, client, out_dir):
        path = out_dir / "primary.png"
        client.call("screenshot", path=str(path), id="primary")
        width, height = png.size(path)
        red, green, blue = png.pixel(path, width // 8, height // 2)[:3]
        assert blue > 150 and red < 120, (red, green, blue)
        print(f"\n  PNG: {path} ({width}x{height})")

    def test_dark_theme_is_darker(self, client, out_dir):
        light = out_dir / "theme-light.png"
        dark = out_dir / "theme-dark.png"
        client.call("screenshot", path=str(light))
        client.call("set_theme", mode="dark")
        client.call("screenshot", path=str(dark))
        luminance = lambda rgb: 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        light_l, dark_l = luminance(png.mean_color(light)), luminance(png.mean_color(dark))
        assert light_l > 200 and dark_l < 60, (light_l, dark_l)
        print(f"\n  PNG: {light} (L={light_l:.0f})\n  PNG: {dark} (L={dark_l:.0f})")

    def test_hover_changes_pixels(self, client, out_dir):
        client.call("hover", id="primary")
        idle = out_dir / "danger-idle.png"
        hovered = out_dir / "danger-hover.png"
        client.call("screenshot", path=str(idle), id="danger")
        client.call("hover", id="danger")
        client.call("screenshot", path=str(hovered), id="danger")
        width, height = png.size(idle)
        x, y = width // 8, height // 2
        assert png.pixel(idle, x, y) != png.pixel(hovered, x, y)
        print(f"\n  PNG: {idle}\n  PNG: {hovered}")


# ── Preview bundles ───────────────────────────────────────────────────


class TestPreview:
    def test_elements_bundle_and_reuse(self, client, out_dir):
        root = out_dir / "previews"
        manifest = preview.capture(client, root, recipe="elements")
        assert manifest["protocol_version"] == "preview-bundle/v1" and not manifest["cached"]
        assert len(manifest["artifacts"]) == 1 + len(ALL_IDS)
        bundle = Path(manifest["_bundle_dir"])
        for artifact in manifest["artifacts"]:
            width, height = png.size(bundle / artifact["path"])
            assert (width, height) == (artifact["width"], artifact["height"])
        assert json.loads((bundle / "summary.json").read_text(encoding="utf-8"))["element_count"] == len(ALL_IDS)
        again = preview.capture(client, root, recipe="elements")
        assert again["cached"] and again["bundle_id"] == manifest["bundle_id"]
        print(f"\n  Bundle: {bundle}")


# ── Installed CLI, as an agent would run it ───────────────────────────


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-gpui-ui")

    @pytest.fixture(autouse=True)
    def _session(self, tmp_path):
        self.session = tmp_path / "session.json"
        self.env = {**os.environ, "PYTHONPATH": str(HARNESS_ROOT)}
        yield
        self._run(["app", "stop", "--force"], check=False)

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + ["--session", str(self.session)] + args,
            capture_output=True, text=True, encoding="utf-8", check=check, env=self.env,
        )

    def _json(self, args, check=True):
        result = self._run(["--json"] + args, check=check)
        return result, json.loads(result.stdout)

    def test_help_and_version(self):
        assert "inspect" in self._run(["--help"]).stdout
        assert "1.0.0" in self._run(["--version"]).stdout

    def test_component_regression_workflow(self, tmp_path):
        _, started = self._json(["app", "start"])
        assert started["port"] > 0 and started["ping"]["protocol"] == 1

        _, clicked = self._json(["act", "click", "primary", "--times", "2"])
        assert clicked["state"]["gallery"]["clicks"] == 2
        self._run(["act", "click", "disabled"])
        self._run(["check", "gallery", "clicks", "2"])
        self._run(["act", "click", "notifications"])
        self._run(["check", "element", "notifications", "--unchecked", "--kind", "switch"])
        self._run(["check", "element", "switch-disabled", "--checked", "--disabled"])

        shot = tmp_path / "danger.png"
        _, result = self._json(["screenshot", "element", "danger", str(shot)])
        assert png.size(shot) == (result["width"], result["height"])
        red, _, blue = png.pixel(shot, result["width"] // 8, result["height"] // 2)[:3]
        assert red > 180 and blue < 120, "danger button should render red"
        print(f"\n  PNG: {shot}")

        _, stopped = self._json(["app", "stop"])
        assert stopped["stopped"] is True
        _, status = self._json(["app", "status"])
        assert status["running"] is False

    def test_agent_debugging_loop(self):
        self._run(["app", "start"])
        failed, payload = self._json(["check", "element", "primary", "--label", "Wrong"], check=False)
        assert failed.returncode == 1
        assert payload["passed"] is False and "got 'Primary'" in payload["failures"][0]
        self._run(["check", "element", "primary", "--label", "Primary"])

    def test_theme_and_preview(self):
        self._run(["app", "start"])
        _, toggled = self._json(["theme", "toggle"])
        assert toggled == {"theme": "dark", "previous": "light"}
        self._run(["check", "theme", "dark"])
        root = self.session.parent / "previews"
        _, manifest = self._json(["preview", "capture", "--recipe", "window", "--root", str(root)])
        assert manifest["protocol_version"] == "preview-bundle/v1"
        _, latest = self._json(["preview", "latest", "--root", str(root)])
        assert latest["bundle_id"] == manifest["bundle_id"]
        print(f"\n  Bundle: {manifest['_bundle_dir']}")

    def test_start_twice_is_refused(self):
        self._run(["app", "start"])
        second, payload = self._json(["app", "start"], check=False)
        assert second.returncode == 1 and "already running" in payload["error"]
        _, replaced = self._json(["app", "start", "--replace"])
        assert replaced["pid"] > 0

    def test_commands_without_app_fail_clearly(self):
        result, payload = self._json(["inspect", "state"], check=False)
        assert result.returncode == 1 and "app start" in payload["error"]
