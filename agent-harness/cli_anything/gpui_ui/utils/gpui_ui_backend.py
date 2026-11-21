"""Backend for cli-anything-gpui-ui: the real `story` gallery application.

Finds and builds the `story` executable, starts it with `--automation`, stops
it, and talks to its JSON Lines automation server (see `docs/AUTOMATION.md` in
the gpui-ui repository). Nothing here renders or simulates the UI: every state
read, click and screenshot is executed by the running GPUI application.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

EXE_NAME = "story.exe" if os.name == "nt" else "story"
STORY_EXE_ENV = "GPUI_UI_STORY_EXE"
REPO_ENV = "GPUI_UI_REPO"
DEFAULT_START_TIMEOUT = 60.0
DEFAULT_REQUEST_TIMEOUT = 30.0


class BackendError(RuntimeError):
    """The backend is missing, not running, or failed a request."""


class AutomationError(BackendError):
    """The automation server answered a request with `ok: false`."""


# ── Locating the software ─────────────────────────────────────────────


def _looks_like_repo(path: Path) -> bool:
    return (path / "Cargo.toml").is_file() and (path / "crates" / "story").is_dir()


def find_repo(explicit: Optional[str] = None) -> Path:
    """Returns the gpui-ui repository root.

    Order: `explicit`, `$GPUI_UI_REPO`, then the parents of this file (the
    harness lives in `<repo>/agent-harness`, and an editable install keeps it
    there).
    """
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get(REPO_ENV):
        candidates.append(Path(os.environ[REPO_ENV]))
    candidates.extend(Path(__file__).resolve().parents)
    for candidate in candidates:
        if _looks_like_repo(candidate.expanduser().resolve()):
            return candidate.expanduser().resolve()
    raise BackendError(
        "Cannot find the gpui-ui repository (a folder with Cargo.toml and crates/story).\n"
        f"Set {REPO_ENV} to its path, e.g.  {REPO_ENV}=C:\\RustProjects\\gpui-ui"
    )


def find_story(explicit: Optional[str] = None) -> Path:
    """Returns the `story` executable.

    Order: `explicit`, `$GPUI_UI_STORY_EXE`, the repo's `target/debug`, the
    repo's `target/release`, then `PATH`. Raises with build instructions when
    none exists.
    """
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise BackendError(f"story executable not found: {path}")
        return path
    if os.environ.get(STORY_EXE_ENV):
        path = Path(os.environ[STORY_EXE_ENV]).expanduser().resolve()
        if not path.is_file():
            raise BackendError(f"{STORY_EXE_ENV} points to a missing file: {path}")
        return path
    try:
        repo = find_repo()
    except BackendError:
        repo = None
    if repo is not None:
        for profile in ("debug", "release"):
            path = repo / "target" / profile / EXE_NAME
            if path.is_file():
                return path
    on_path = shutil.which("story")
    if on_path:
        return Path(on_path).resolve()
    raise BackendError(
        "The gpui-ui gallery (story) is not built. Build it with:\n"
        "  cli-anything-gpui-ui app build\n"
        "or, in the gpui-ui repository:\n"
        "  cargo build -p story\n"
        "It needs Rust (cargo) and, for screenshots, the default `screenshot` feature."
    )


def build_story(release: bool = False, repo: Optional[str] = None) -> dict[str, Any]:
    """Builds `story` with cargo and returns the executable path."""
    cargo = shutil.which("cargo")
    if not cargo:
        raise BackendError("cargo is not installed or not on PATH; install Rust from https://rustup.rs")
    root = find_repo(repo)
    args = [cargo, "build", "-p", "story"]
    if release:
        args.append("--release")
    started = time.monotonic()
    result = subprocess.run(args, cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-30:])
        raise BackendError(f"cargo build failed (exit {result.returncode}):\n{tail}")
    exe = root / "target" / ("release" if release else "debug") / EXE_NAME
    return {
        "exe": str(exe),
        "profile": "release" if release else "debug",
        "seconds": round(time.monotonic() - started, 1),
    }


# ── Process management ────────────────────────────────────────────────


def pid_alive(pid: int) -> bool:
    """Reports whether a process with `pid` is running, without signalling it."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def kill_process(pid: int) -> None:
    """Force-terminates `pid`. Used only when `quit` did not end the app."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        import signal

        os.kill(pid, signal.SIGKILL)


def _read_listening_port(log_path: Path) -> Optional[int]:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "listening":
            return int(event["port"])
    return None


def start_story(
    exe: Path,
    log_path: Path,
    port: int = 0,
    timeout: float = DEFAULT_START_TIMEOUT,
) -> dict[str, Any]:
    """Starts `story --automation` detached from this process.

    The app outlives the CLI command; its stdout/stderr go to `log_path`. Waits
    until the server prints its `listening` line and answers `ping`.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "w", encoding="utf-8")
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(
            [str(exe), "--automation", "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            **kwargs,
        )
    finally:
        log.close()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        bound = _read_listening_port(log_path)
        if bound is not None:
            info = AutomationClient(bound).call("ping")
            return {"pid": process.pid, "port": bound, "exe": str(exe), "log": str(log_path), "ping": info}
        code = process.poll()
        if code is not None:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise BackendError(f"story exited with code {code} before listening. Log:\n{tail}")
        time.sleep(0.1)
    kill_process(process.pid)
    raise BackendError(f"story did not start listening within {timeout:.0f}s; see {log_path}")


# ── Automation client ─────────────────────────────────────────────────


class AutomationClient:
    """One request per connection to the story automation server."""

    def __init__(self, port: int, host: str = "127.0.0.1", timeout: float = DEFAULT_REQUEST_TIMEOUT):
        self.port = port
        self.host = host
        self.timeout = timeout

    def request(self, cmd: str, **params: Any) -> dict[str, Any]:
        """Sends one request and returns the raw response object."""
        payload = json.dumps({"cmd": cmd, **params}) + "\n"
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(payload.encode("utf-8"))
                with sock.makefile("r", encoding="utf-8") as reader:
                    line = reader.readline()
        except OSError as error:
            raise BackendError(
                f"cannot reach the gallery on {self.host}:{self.port} ({error}). "
                "Is it running? Start it with: cli-anything-gpui-ui app start"
            ) from error
        if not line:
            raise BackendError(f"the gallery closed the connection during `{cmd}`")
        try:
            return json.loads(line)
        except json.JSONDecodeError as error:
            raise BackendError(f"invalid response to `{cmd}`: {line!r}") from error

    def call(self, cmd: str, **params: Any) -> Any:
        """Sends one request and returns its `result`, raising on `ok: false`."""
        response = self.request(cmd, **params)
        if not response.get("ok"):
            raise AutomationError(response.get("error") or f"`{cmd}` failed")
        return response.get("result")


def absolute_output_path(path: str) -> str:
    """Resolves `path` against the CLI's working directory.

    The app has its own working directory, so relative paths must be resolved
    here before they are sent.
    """
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return str(resolved)
