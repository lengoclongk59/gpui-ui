"""cli-anything-gpui-ui: drive and test the gpui-ui component gallery.

The real software is the `story` gallery application built from the gpui-ui
repository. This CLI starts it with `--automation`, then inspects, clicks,
checks and screenshots its components through that server.
"""

from __future__ import annotations

import functools
import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

import click

from cli_anything.gpui_ui import __version__
from cli_anything.gpui_ui.core import checks
from cli_anything.gpui_ui.core import png
from cli_anything.gpui_ui.core import preview as preview_mod
from cli_anything.gpui_ui.core import state as state_mod
from cli_anything.gpui_ui.core.session import AppSession, SessionStore
from cli_anything.gpui_ui.utils import gpui_ui_backend as backend
from cli_anything.gpui_ui.utils.repl_skin import ReplSkin

PROG = "cli-anything-gpui-ui"
STOP_TIMEOUT = 10.0

_repl_mode = False


class Obj:
    """Per-invocation context shared by all commands."""

    def __init__(self, use_json: bool, session_path: Optional[str]):
        self.use_json = use_json
        self.store = SessionStore(Path(session_path) if session_path else None)
        self.skin = ReplSkin("gpui_ui", version=__version__, history_file=str(self.store.directory / "history"))


class CommandFailed(Exception):
    """A command finished but its outcome is a failure (e.g. a failed check)."""

    def __init__(self, payload: dict[str, Any], message: str):
        super().__init__(message)
        self.payload = payload


# ── Output helpers ────────────────────────────────────────────────────


def emit(obj: Obj, data: Any, human: Optional[Callable[[], None]] = None) -> None:
    """Prints `data` as JSON in --json mode, otherwise runs `human`."""
    if obj.use_json:
        click.echo(json.dumps(data, indent=2))
    elif human is not None:
        human()
    else:
        click.echo(json.dumps(data, indent=2))


def handle_errors(func: Callable) -> Callable:
    """Turns backend and lookup errors into a clear message and exit code 1."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx = click.get_current_context()
        obj: Obj = ctx.obj
        try:
            return func(*args, **kwargs)
        except CommandFailed as failure:
            emit(obj, failure.payload, lambda: obj.skin.error(str(failure)))
            ctx.exit(1)
        except (
            backend.BackendError,
            state_mod.ElementNotFound,
            png.PngError,
            ValueError,
            OSError,
        ) as error:
            payload = {"error": str(error), "type": type(error).__name__}
            emit(obj, payload, lambda: obj.skin.error(str(error)))
            ctx.exit(1)

    return wrapper


def _client(obj: Obj) -> backend.AutomationClient:
    session = obj.store.load()
    if session is None:
        raise backend.BackendError(f"no gallery is running; start it with: {PROG} app start")
    if not backend.pid_alive(session.pid):
        raise backend.BackendError(
            f"the gallery (pid {session.pid}) is no longer running; start it with: {PROG} app start"
        )
    return backend.AutomationClient(session.port)


def _print_state(obj: Obj, state: dict[str, Any]) -> None:
    summary = state_mod.summarize(state)
    obj.skin.status("theme", str(summary["theme"]))
    for key, value in summary["gallery"].items():
        obj.skin.status(f"gallery.{key}", json.dumps(value))
    obj.skin.status("elements", str(summary["element_count"]))


def _print_elements(obj: Obj, items: list[dict[str, Any]]) -> None:
    obj.skin.table(state_mod.ELEMENT_HEADERS, [state_mod.element_row(item) for item in items])


def _require_check(obj: Obj, result: dict[str, Any]) -> None:
    if not result["passed"]:
        raise CommandFailed(result, "; ".join(result["failures"]))
    emit(obj, result, lambda: obj.skin.success(f"check passed: {result['check']}"))


# ── Main group ────────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Print machine-readable JSON.")
@click.option(
    "--session",
    "session_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Session file (default ~/.cli-anything-gpui-ui/session.json or $CLI_ANYTHING_GPUI_UI_SESSION).",
)
@click.version_option(__version__, prog_name=PROG)
@click.pass_context
def cli(ctx: click.Context, use_json: bool, session_path: Optional[str]) -> None:
    """Drive and test the gpui-ui component gallery (the `story` app).

    Start the app with `app start`, then use inspect / act / check / screenshot /
    preview. With no subcommand, opens an interactive REPL.
    """
    ctx.obj = Obj(use_json, session_path)
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── app ───────────────────────────────────────────────────────────────


@cli.group()
def app() -> None:
    """Build, start, stop and check the gallery application."""


@app.command("build")
@click.option("--release", is_flag=True, help="Build the optimized profile.")
@click.pass_obj
@handle_errors
def app_build(obj: Obj, release: bool) -> None:
    """Build `story` with cargo (the first build takes several minutes)."""
    if not obj.use_json:
        obj.skin.info("cargo build -p story" + (" --release" if release else "") + " ...")
    result = backend.build_story(release=release)
    emit(obj, result, lambda: obj.skin.success(f"built {result['exe']} in {result['seconds']}s"))


@app.command("start")
@click.option("--port", type=int, default=0, show_default=True, help="Automation port; 0 picks a free one.")
@click.option("--exe", type=click.Path(dir_okay=False), default=None, help="Path to the story executable.")
@click.option("--replace", is_flag=True, help="Stop a running gallery from this session first.")
@click.option("--timeout", type=float, default=backend.DEFAULT_START_TIMEOUT, show_default=True)
@click.pass_obj
@handle_errors
def app_start(obj: Obj, port: int, exe: Optional[str], replace: bool, timeout: float) -> None:
    """Launch the gallery with its automation server and record the session."""
    existing = obj.store.load()
    if existing is not None and backend.pid_alive(existing.pid):
        if not replace:
            raise backend.BackendError(
                f"a gallery is already running (pid {existing.pid}, port {existing.port}); "
                f"use `{PROG} app stop` or `app start --replace`"
            )
        _stop(obj, existing)
    story = backend.find_story(exe)
    started = backend.start_story(story, obj.store.log_path, port=port, timeout=timeout)
    session = AppSession(pid=started["pid"], port=started["port"], exe=started["exe"], log=started["log"])
    obj.store.save(session)
    result = {**session.to_dict(), "session": str(obj.store.path), "ping": started["ping"]}
    emit(obj, result, lambda: obj.skin.success(f"gallery running: pid {session.pid}, port {session.port}"))


def _stop(obj: Obj, session: AppSession, force: bool = False) -> dict[str, Any]:
    method = "quit"
    if not force:
        try:
            backend.AutomationClient(session.port, timeout=5).call("quit")
        except backend.BackendError:
            method = "kill"
    deadline = time.monotonic() + STOP_TIMEOUT
    while (not force) and backend.pid_alive(session.pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    if backend.pid_alive(session.pid):
        backend.kill_process(session.pid)
        method = "kill"
    obj.store.clear()
    return {"stopped": True, "pid": session.pid, "method": method}


@app.command("stop")
@click.option("--force", is_flag=True, help="Kill the process instead of asking it to quit.")
@click.pass_obj
@handle_errors
def app_stop(obj: Obj, force: bool) -> None:
    """Close the gallery. Safe to run when nothing is running."""
    session = obj.store.load()
    if session is None or not backend.pid_alive(session.pid):
        obj.store.clear()
        result = {"stopped": False, "reason": "not running"}
        emit(obj, result, lambda: obj.skin.info("no gallery is running"))
        return
    result = _stop(obj, session, force=force)
    emit(obj, result, lambda: obj.skin.success(f"gallery stopped (pid {result['pid']}, {result['method']})"))


@app.command("status")
@click.pass_obj
@handle_errors
def app_status(obj: Obj) -> None:
    """Report whether the gallery is running and reachable."""
    session = obj.store.load()
    result: dict[str, Any] = {"running": False, "session": str(obj.store.path)}
    if session is not None:
        result.update(session.to_dict())
        result["running"] = backend.pid_alive(session.pid)
        if result["running"]:
            try:
                result["ping"] = backend.AutomationClient(session.port, timeout=5).call("ping")
                result["reachable"] = True
            except backend.BackendError as error:
                result["reachable"] = False
                result["error"] = str(error)

    def human() -> None:
        if not result["running"]:
            obj.skin.warning("gallery is not running")
            return
        obj.skin.status("pid", str(result["pid"]))
        obj.skin.status("port", str(result["port"]))
        obj.skin.status("reachable", "yes" if result.get("reachable") else "no")
        obj.skin.status("exe", result["exe"])
        obj.skin.status("log", result["log"])

    emit(obj, result, human)


@app.command("ping")
@click.pass_obj
@handle_errors
def app_ping(obj: Obj) -> None:
    """Check the automation server and report its protocol version."""
    result = _client(obj).call("ping")
    emit(obj, result, lambda: obj.skin.success(f"{result['app']} {result['version']}, protocol {result['protocol']}"))


# ── inspect ───────────────────────────────────────────────────────────


@cli.group()
def inspect() -> None:
    """Read the gallery state without changing it."""


@inspect.command("state")
@click.pass_obj
@handle_errors
def inspect_state(obj: Obj) -> None:
    """Theme, gallery values and every element."""
    state = _client(obj).call("state")

    def human() -> None:
        _print_state(obj, state)
        _print_elements(obj, state["elements"])

    emit(obj, state, human)


@inspect.command("elements")
@click.option("--kind", default=None, help="Only elements of this kind (button, switch, ...).")
@click.pass_obj
@handle_errors
def inspect_elements(obj: Obj, kind: Optional[str]) -> None:
    """List probed elements."""
    items = state_mod.elements(_client(obj).call("state"), kind)
    emit(obj, items, lambda: _print_elements(obj, items))


@inspect.command("element")
@click.argument("element_id")
@click.pass_obj
@handle_errors
def inspect_element(obj: Obj, element_id: str) -> None:
    """Show one element by test id."""
    item = state_mod.find_element(_client(obj).call("state"), element_id)
    emit(obj, item, lambda: _print_elements(obj, [item]))


# ── act ───────────────────────────────────────────────────────────────


@cli.group()
def act() -> None:
    """Send pointer input to components (real GPUI mouse events)."""


@act.command("click")
@click.argument("element_id")
@click.option("--times", type=click.IntRange(min=1), default=1, show_default=True)
@click.pass_obj
@handle_errors
def act_click(obj: Obj, element_id: str, times: int) -> None:
    """Click an element's center; returns the state after the last click."""
    client = _client(obj)
    state: dict[str, Any] = {}
    for _ in range(times):
        state = client.call("click", id=element_id)
    result = {"clicked": element_id, "times": times, "element": state_mod.find_element(state, element_id), "state": state}

    def human() -> None:
        obj.skin.success(f"clicked {element_id} x{times}")
        _print_state(obj, state)

    emit(obj, result, human)


@act.command("hover")
@click.argument("element_id")
@click.pass_obj
@handle_errors
def act_hover(obj: Obj, element_id: str) -> None:
    """Move the pointer over an element (shows its hover style)."""
    state = _client(obj).call("hover", id=element_id)
    result = {"hovered": element_id, "state": state}
    emit(obj, result, lambda: obj.skin.success(f"hovering {element_id}"))


# ── theme ─────────────────────────────────────────────────────────────

THEMES = click.Choice(["light", "dark"])


@cli.group()
def theme() -> None:
    """Read or switch the light/dark theme."""


@theme.command("get")
@click.pass_obj
@handle_errors
def theme_get(obj: Obj) -> None:
    """Show the active theme."""
    current = _client(obj).call("state")["theme"]
    emit(obj, {"theme": current}, lambda: obj.skin.status("theme", current))


@theme.command("set")
@click.argument("mode", type=THEMES)
@click.pass_obj
@handle_errors
def theme_set(obj: Obj, mode: str) -> None:
    """Switch to MODE (light or dark)."""
    state = _client(obj).call("set_theme", mode=mode)
    emit(obj, {"theme": state["theme"]}, lambda: obj.skin.success(f"theme is {state['theme']}"))


@theme.command("toggle")
@click.pass_obj
@handle_errors
def theme_toggle(obj: Obj) -> None:
    """Switch between light and dark."""
    client = _client(obj)
    current = client.call("state")["theme"]
    state = client.call("set_theme", mode="dark" if current == "light" else "light")
    emit(obj, {"theme": state["theme"], "previous": current}, lambda: obj.skin.success(f"theme is {state['theme']}"))


# ── check ─────────────────────────────────────────────────────────────


@cli.group()
def check() -> None:
    """Assert gallery state; exits with code 1 when a check fails."""


@check.command("element")
@click.argument("element_id")
@click.option("--kind", default=None)
@click.option("--label", default=None)
@click.option("--disabled/--enabled", "disabled", default=None)
@click.option("--checked/--unchecked", "checked", default=None)
@click.pass_obj
@handle_errors
def check_element(
    obj: Obj,
    element_id: str,
    kind: Optional[str],
    label: Optional[str],
    disabled: Optional[bool],
    checked: Optional[bool],
) -> None:
    """Assert an element's kind, label, disabled and checked values."""
    state = _client(obj).call("state")
    _require_check(obj, checks.check_element(state, element_id, kind=kind, label=label, disabled=disabled, checked=checked))


@check.command("gallery")
@click.argument("key")
@click.argument("expected")
@click.pass_obj
@handle_errors
def check_gallery(obj: Obj, key: str, expected: str) -> None:
    """Assert a gallery value; EXPECTED is parsed as JSON (3, true, "x")."""
    state = _client(obj).call("state")
    _require_check(obj, checks.check_gallery(state, key, checks.parse_expected(expected)))


@check.command("theme")
@click.argument("mode", type=THEMES)
@click.pass_obj
@handle_errors
def check_theme(obj: Obj, mode: str) -> None:
    """Assert the active theme."""
    _require_check(obj, checks.check_theme(_client(obj).call("state"), mode))


# ── screenshot ────────────────────────────────────────────────────────


def _verified_shot(result: dict[str, Any]) -> dict[str, Any]:
    width, height = png.size(result["path"])
    if (width, height) != (result["width"], result["height"]):
        raise png.PngError(f"{result['path']} is {width}x{height}, backend reported {result['width']}x{result['height']}")
    return {**result, "bytes": os.path.getsize(result["path"])}


@cli.group()
def screenshot() -> None:
    """Render PNGs with GPUI's offscreen renderer (no screen capture)."""


@screenshot.command("window")
@click.argument("output", type=click.Path(dir_okay=False))
@click.pass_obj
@handle_errors
def screenshot_window(obj: Obj, output: str) -> None:
    """Render the whole gallery window to OUTPUT."""
    result = _verified_shot(_client(obj).call("screenshot", path=backend.absolute_output_path(output)))
    emit(obj, result, lambda: obj.skin.success(f"{result['path']} ({result['width']}x{result['height']})"))


@screenshot.command("element")
@click.argument("element_id")
@click.argument("output", type=click.Path(dir_okay=False))
@click.pass_obj
@handle_errors
def screenshot_element(obj: Obj, element_id: str, output: str) -> None:
    """Render one element, cropped to its bounds, to OUTPUT."""
    result = _verified_shot(
        _client(obj).call("screenshot", path=backend.absolute_output_path(output), id=element_id)
    )
    emit(obj, result, lambda: obj.skin.success(f"{result['path']} ({result['width']}x{result['height']})"))


# ── preview ───────────────────────────────────────────────────────────


@cli.group()
def preview() -> None:
    """Publish preview-bundle/v1 bundles (inspect them with `cli-hub previews`)."""


@preview.command("recipes")
@click.pass_obj
@handle_errors
def preview_recipes(obj: Obj) -> None:
    """List the preview recipes."""
    items = preview_mod.recipes()
    emit(obj, items, lambda: obj.skin.table(["recipe", "description"], [[i["recipe"], i["description"]] for i in items]))


def _preview_root(obj: Obj, root: Optional[str]) -> Path:
    return Path(root).expanduser().resolve() if root else obj.store.preview_root


@preview.command("capture")
@click.option("--recipe", type=click.Choice(list(preview_mod.RECIPES)), default="elements", show_default=True)
@click.option("--force", is_flag=True, help="Render a new bundle even if the state is unchanged.")
@click.option("--root", type=click.Path(file_okay=False), default=None, help="Bundle root (default: next to the session file).")
@click.pass_obj
@handle_errors
def preview_capture(obj: Obj, recipe: str, force: bool, root: Optional[str]) -> None:
    """Render a bundle for the current gallery state."""
    session = obj.store.load()
    source = {"pid": session.pid, "port": session.port, "exe": session.exe} if session else {}
    manifest = preview_mod.capture(_client(obj), _preview_root(obj, root), recipe=recipe, force=force, source=source)

    def human() -> None:
        obj.skin.success(("reused " if manifest["cached"] else "published ") + manifest["bundle_id"])
        obj.skin.status("bundle", manifest["_bundle_dir"])
        obj.skin.status("artifacts", str(len(manifest["artifacts"])))
        obj.skin.hint(f"inspect with: cli-hub previews inspect {manifest['_bundle_dir']}")

    emit(obj, manifest, human)


@preview.command("latest")
@click.option("--recipe", type=click.Choice(list(preview_mod.RECIPES)), default=None)
@click.option("--root", type=click.Path(file_okay=False), default=None)
@click.pass_obj
@handle_errors
def preview_latest(obj: Obj, recipe: Optional[str], root: Optional[str]) -> None:
    """Show the newest bundle without rendering."""
    manifest = preview_mod.latest(_preview_root(obj, root), recipe)
    if manifest is None:
        raise backend.BackendError(f"no preview bundle yet; publish one with: {PROG} preview capture")
    emit(obj, manifest, lambda: obj.skin.status("bundle", manifest["_bundle_dir"]))


# ── REPL ──────────────────────────────────────────────────────────────

REPL_HELP = {
    "app start | stop | status | ping | build": "manage the gallery process",
    "inspect state | elements [--kind K] | element ID": "read state",
    "act click ID [--times N] | hover ID": "pointer input",
    "theme get | set light|dark | toggle": "theme",
    "check element ID [--checked] [--disabled] ...": "assert element values",
    "check gallery KEY VALUE | theme MODE": "assert gallery values / theme",
    "screenshot window OUT | element ID OUT": "render PNGs",
    "preview recipes | capture [--recipe R] | latest": "preview bundles",
    "help | quit": "this help / leave",
}


def _split(line: str) -> list[str]:
    parts = shlex.split(line, posix=False)
    return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]


@cli.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Interactive shell (the default when no subcommand is given)."""
    global _repl_mode
    obj: Obj = ctx.obj
    skin = obj.skin
    _repl_mode = True
    obj.store.directory.mkdir(parents=True, exist_ok=True)
    skin.print_banner()
    # prompt_toolkit needs a real console; piped input (agents, scripts,
    # mintty) falls back to plain input().
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    pt_session = skin.create_prompt_session() if interactive else None
    base_args = ["--session", str(obj.store.path)] + (["--json"] if obj.use_json else [])
    try:
        while True:
            try:
                session = obj.store.load()
                label = f"pid {session.pid}" if session and backend.pid_alive(session.pid) else "stopped"
                line = skin.get_input(pt_session, project_name=label)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception:  # prompt_toolkit cannot drive this terminal
                if pt_session is None:
                    raise
                pt_session = None
                continue
            if not line:
                continue
            if line in {"quit", "exit", "q"}:
                break
            if line in {"help", "?"}:
                skin.help(REPL_HELP)
                continue
            try:
                args = _split(line)
            except ValueError as error:
                skin.error(f"cannot parse: {error}")
                continue
            if args and args[0] == "repl":
                skin.warning("already in the REPL")
                continue
            try:
                cli.main(args=base_args + args, prog_name=PROG, standalone_mode=False)
            except click.exceptions.Exit:
                pass
            except click.ClickException as error:
                skin.error(error.format_message())
            except click.exceptions.Abort:
                skin.warning("aborted")
    finally:
        _repl_mode = False
    skin.print_goodbye()


def _configure_streams() -> None:
    # Agents read output through pipes; make those UTF-8 so status glyphs never
    # raise UnicodeEncodeError on Windows code pages.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        if stream.isatty():
            reconfigure(errors="replace")
        else:
            reconfigure(encoding="utf-8")


def main() -> None:
    _configure_streams()
    cli(prog_name=PROG)


if __name__ == "__main__":
    main()
