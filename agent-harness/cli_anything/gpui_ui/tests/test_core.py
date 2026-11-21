"""Unit tests: synthetic data and a fake automation server, no GPU window."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_anything.gpui_ui.core import checks
from cli_anything.gpui_ui.core import png
from cli_anything.gpui_ui.core import preview
from cli_anything.gpui_ui.core import state as state_mod
from cli_anything.gpui_ui.core.session import SESSION_ENV, AppSession, SessionStore, default_session_path
from cli_anything.gpui_ui.gpui_ui_cli import cli
from cli_anything.gpui_ui.tests.fake_story import FakeGallery, FakeStory, encode_png
from cli_anything.gpui_ui.utils import gpui_ui_backend as backend

REPO = Path(__file__).resolve().parents[4]


@pytest.fixture
def sample_state():
    return FakeGallery().state()


@pytest.fixture
def fake():
    with FakeStory() as server:
        yield server


@pytest.fixture
def session_file(tmp_path, fake):
    """A session pointing at the fake server, with this process as the 'app'."""
    store = SessionStore(tmp_path / "session.json")
    store.save(AppSession(pid=os.getpid(), port=fake.port, exe="fake-story", log=str(tmp_path / "story.log")))
    return store.path


def run_cli(session_file, *args):
    result = CliRunner().invoke(cli, ["--session", str(session_file), *args], catch_exceptions=False)
    return result


# ── core/state.py ─────────────────────────────────────────────────────


class TestState:
    def test_elements_filters_by_kind(self, sample_state):
        assert [e["id"] for e in state_mod.elements(sample_state, "switch")] == ["notifications"]
        assert len(state_mod.elements(sample_state)) == 4

    def test_find_element(self, sample_state):
        assert state_mod.find_element(sample_state, "primary")["label"] == "Primary"

    def test_find_element_lists_known_ids(self, sample_state):
        with pytest.raises(state_mod.ElementNotFound, match="known ids: disabled, notifications"):
            state_mod.find_element(sample_state, "nope")

    def test_summarize_counts_kinds(self, sample_state):
        summary = state_mod.summarize(sample_state)
        assert summary["element_count"] == 4
        assert summary["kinds"] == {"button": 3, "switch": 1}
        assert summary["theme"] == "light"

    def test_element_row_formats_checked(self, sample_state):
        switch = state_mod.element_row(state_mod.find_element(sample_state, "notifications"))
        button = state_mod.element_row(state_mod.find_element(sample_state, "primary"))
        assert switch[4] == "on" and button[4] == "-"

    def test_element_row_formats_bounds(self, sample_state):
        row = state_mod.element_row(state_mod.find_element(sample_state, "primary"))
        assert row[5] == "210,20 80x36"


# ── core/checks.py ────────────────────────────────────────────────────


class TestChecks:
    def test_element_passes(self, sample_state):
        result = checks.check_element(sample_state, "notifications", kind="switch", checked=True, disabled=False)
        assert result["passed"] and result["failures"] == []

    @pytest.mark.parametrize(
        "field, value",
        [("kind", "switch"), ("label", "Other"), ("disabled", True), ("checked", False)],
    )
    def test_element_fails_per_field(self, sample_state, field, value):
        result = checks.check_element(sample_state, "primary", **{field: value})
        assert not result["passed"]
        assert result["failures"][0].startswith(f"primary.{field}: expected")

    def test_element_ignores_unset_expectations(self, sample_state):
        assert checks.check_element(sample_state, "primary")["passed"]

    def test_element_unknown_id_raises(self, sample_state):
        with pytest.raises(state_mod.ElementNotFound):
            checks.check_element(sample_state, "nope", label="x")

    @pytest.mark.parametrize("raw, parsed", [("3", 3), ("true", True), ('"on"', "on"), ("on", "on")])
    def test_parse_expected(self, raw, parsed):
        assert checks.parse_expected(raw) == parsed

    def test_gallery_pass_and_fail(self, sample_state):
        assert checks.check_gallery(sample_state, "clicks", 0)["passed"]
        failed = checks.check_gallery(sample_state, "clicks", 5)
        assert not failed["passed"] and "expected 5, got 0" in failed["failures"][0]

    def test_gallery_unknown_key(self, sample_state):
        result = checks.check_gallery(sample_state, "volume", 1)
        assert not result["passed"] and "known keys: clicks, notifications" in result["failures"][0]

    def test_theme(self, sample_state):
        assert checks.check_theme(sample_state, "light")["passed"]
        assert not checks.check_theme(sample_state, "dark")["passed"]


# ── core/session.py ───────────────────────────────────────────────────


class TestSession:
    def test_round_trip(self, tmp_path):
        store = SessionStore(tmp_path / "s.json")
        session = AppSession(pid=12, port=3456, exe="story", log="log.txt")
        store.save(session)
        assert store.load() == session

    def test_missing_file_is_none(self, tmp_path):
        assert SessionStore(tmp_path / "absent.json").load() is None

    def test_clear(self, tmp_path):
        store = SessionStore(tmp_path / "s.json")
        store.save(AppSession(pid=1, port=2, exe="e", log="l"))
        store.clear()
        assert store.load() is None

    def test_missing_keys_rejected(self):
        with pytest.raises(ValueError, match="missing"):
            AppSession.from_dict({"pid": 1})

    def test_shorter_save_leaves_no_stale_bytes(self, tmp_path):
        store = SessionStore(tmp_path / "s.json")
        store.save(AppSession(pid=1, port=2, exe="x" * 500, log="l"))
        store.save(AppSession(pid=1, port=2, exe="short", log="l"))
        assert json.loads(store.path.read_text(encoding="utf-8"))["exe"] == "short"

    def test_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv(SESSION_ENV, str(tmp_path / "custom.json"))
        assert default_session_path() == (tmp_path / "custom.json").resolve()


# ── core/png.py ───────────────────────────────────────────────────────


class TestPng:
    def test_size(self, tmp_path):
        path = tmp_path / "a.png"
        path.write_bytes(encode_png(7, 3, (1, 2, 3, 255)))
        assert png.size(path) == (7, 3)

    @pytest.mark.parametrize("filter_type", [0, 1, 2, 3, 4])
    def test_pixel_through_every_filter(self, tmp_path, filter_type):
        path = tmp_path / "a.png"
        path.write_bytes(encode_png(5, 4, (37, 99, 235, 255), filter_type))
        assert png.pixel(path, 4, 3) == (37, 99, 235, 255)

    def test_mean_color(self, tmp_path):
        path = tmp_path / "a.png"
        path.write_bytes(encode_png(4, 4, (10, 20, 30, 255)))
        assert png.mean_color(path) == (10, 20, 30)

    def test_not_png(self, tmp_path):
        path = tmp_path / "a.png"
        path.write_bytes(b"GIF89a....")
        with pytest.raises(png.PngError, match="not a PNG"):
            png.size(path)

    def test_pixel_out_of_range(self, tmp_path):
        path = tmp_path / "a.png"
        path.write_bytes(encode_png(2, 2, (0, 0, 0, 255)))
        with pytest.raises(png.PngError, match="outside"):
            png.pixel(path, 2, 0)


# ── utils/gpui_ui_backend.py ──────────────────────────────────────────


class TestBackend:
    def test_find_repo_from_package_location(self, monkeypatch):
        monkeypatch.delenv(backend.REPO_ENV, raising=False)
        assert backend.find_repo() == REPO

    def test_find_repo_env(self, monkeypatch):
        monkeypatch.setenv(backend.REPO_ENV, str(REPO))
        assert backend.find_repo() == REPO

    def test_find_repo_explicit_invalid_falls_back(self, tmp_path, monkeypatch):
        # An invalid explicit path is skipped; the package location still works.
        monkeypatch.delenv(backend.REPO_ENV, raising=False)
        assert backend.find_repo(str(tmp_path)) == REPO

    def test_find_story_explicit_missing(self, tmp_path):
        with pytest.raises(backend.BackendError, match="not found"):
            backend.find_story(str(tmp_path / "nope.exe"))

    def test_find_story_env(self, tmp_path, monkeypatch):
        exe = tmp_path / backend.EXE_NAME
        exe.write_bytes(b"")
        monkeypatch.setenv(backend.STORY_EXE_ENV, str(exe))
        assert backend.find_story() == exe.resolve()

    def test_read_listening_port(self, tmp_path):
        log = tmp_path / "story.log"
        log.write_text('noise\n{"event":"listening","port":4242}\n', encoding="utf-8")
        assert backend._read_listening_port(log) == 4242
        assert backend._read_listening_port(tmp_path / "absent.log") is None

    def test_pid_alive(self):
        assert backend.pid_alive(os.getpid())
        assert not backend.pid_alive(0)
        assert not backend.pid_alive(2**22 + 1)

    def test_client_success_and_error(self, fake):
        client = backend.AutomationClient(fake.port)
        assert client.call("ping")["protocol"] == 1
        with pytest.raises(backend.AutomationError, match="known ids"):
            client.call("click", id="nope")

    def test_client_unreachable(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            closed_port = probe.getsockname()[1]
        with pytest.raises(backend.BackendError, match="cannot reach"):
            backend.AutomationClient(closed_port, timeout=2).call("ping")

    def test_absolute_output_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resolved = backend.absolute_output_path("shots/a.png")
        assert Path(resolved) == (tmp_path / "shots" / "a.png").resolve()
        assert (tmp_path / "shots").is_dir()


# ── core/preview.py ───────────────────────────────────────────────────


class TestPreview:
    def test_recipes(self):
        assert {r["recipe"] for r in preview.recipes()} == {"window", "elements"}

    def test_capture_elements_bundle(self, fake, tmp_path):
        manifest = preview.capture(backend.AutomationClient(fake.port), tmp_path, recipe="elements")
        assert manifest["protocol_version"] == "preview-bundle/v1"
        assert manifest["cached"] is False
        roles = [a["role"] for a in manifest["artifacts"]]
        assert roles.count("hero") == 1 and roles.count("gallery") == 4
        for artifact in manifest["artifacts"]:
            png.size(Path(manifest["_bundle_dir"]) / artifact["path"])
        assert (Path(manifest["_bundle_dir"]) / "summary.json").is_file()

    def test_unchanged_state_reuses_bundle(self, fake, tmp_path):
        client = backend.AutomationClient(fake.port)
        first = preview.capture(client, tmp_path, recipe="window")
        second = preview.capture(client, tmp_path, recipe="window")
        assert second["cached"] is True and second["bundle_id"] == first["bundle_id"]
        client.call("click", id="primary")
        third = preview.capture(client, tmp_path, recipe="window")
        assert third["cached"] is False and third["bundle_id"] != first["bundle_id"]

    def test_latest(self, fake, tmp_path):
        assert preview.latest(tmp_path) is None
        published = preview.capture(backend.AutomationClient(fake.port), tmp_path, recipe="window")
        assert preview.latest(tmp_path, "window")["bundle_id"] == published["bundle_id"]


# ── CLI (CliRunner against the fake server) ───────────────────────────


class TestCli:
    def test_no_session_is_a_clear_error(self, tmp_path):
        result = CliRunner().invoke(cli, ["--session", str(tmp_path / "none.json"), "--json", "inspect", "state"])
        assert result.exit_code == 1
        assert "app start" in json.loads(result.output)["error"]

    def test_status_without_session(self, tmp_path):
        result = CliRunner().invoke(cli, ["--session", str(tmp_path / "none.json"), "--json", "app", "status"])
        assert result.exit_code == 0 and json.loads(result.output)["running"] is False

    def test_inspect_state_json(self, session_file):
        result = run_cli(session_file, "--json", "inspect", "state")
        assert result.exit_code == 0
        assert json.loads(result.output)["gallery"] == {"clicks": 0, "notifications": True}

    def test_click_times(self, session_file, fake):
        result = run_cli(session_file, "--json", "act", "click", "primary", "--times", "3")
        assert result.exit_code == 0
        assert json.loads(result.output)["state"]["gallery"]["clicks"] == 3
        assert [r["cmd"] for r in fake.gallery.requests].count("click") == 3

    def test_check_pass_and_fail_exit_codes(self, session_file):
        assert run_cli(session_file, "check", "gallery", "clicks", "0").exit_code == 0
        failed = run_cli(session_file, "--json", "check", "element", "primary", "--label", "Wrong")
        assert failed.exit_code == 1
        payload = json.loads(failed.output)
        assert payload["passed"] is False and "got 'Primary'" in payload["failures"][0]

    def test_check_switch_flags(self, session_file):
        assert run_cli(session_file, "check", "element", "notifications", "--checked", "--enabled").exit_code == 0
        assert run_cli(session_file, "check", "element", "notifications", "--unchecked").exit_code == 1

    def test_theme_toggle(self, session_file):
        result = run_cli(session_file, "--json", "theme", "toggle")
        assert json.loads(result.output) == {"theme": "dark", "previous": "light"}

    def test_screenshot_element_is_verified(self, session_file, tmp_path):
        out = tmp_path / "shots" / "primary.png"
        result = run_cli(session_file, "--json", "screenshot", "element", "primary", str(out))
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert (payload["width"], payload["height"]) == png.size(out) == (80, 36)
        assert payload["bytes"] > 0

    def test_unknown_element_error(self, session_file):
        result = run_cli(session_file, "--json", "act", "click", "nope")
        assert result.exit_code == 1
        assert json.loads(result.output)["type"] == "AutomationError"

    def test_repl_with_piped_input(self, session_file):
        result = CliRunner().invoke(
            cli,
            ["--session", str(session_file)],
            input="act click primary\ncheck gallery clicks 1\nhelp\nquit\n",
        )
        assert result.exit_code == 0, result.output
        assert "clicked primary" in result.output
        assert "check passed: gallery clicks" in result.output
