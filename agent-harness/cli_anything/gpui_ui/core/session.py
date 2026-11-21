"""The app session: which `story` process this CLI drives, persisted as JSON.

Every command reads the session file to find the running gallery. Saves use
exclusive locking (see CLI-Anything `guides/session-locking.md`).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SESSION_ENV = "CLI_ANYTHING_GPUI_UI_SESSION"
DEFAULT_SESSION_DIR = Path.home() / ".cli-anything-gpui-ui"


def default_session_path() -> Path:
    if os.environ.get(SESSION_ENV):
        return Path(os.environ[SESSION_ENV]).expanduser().resolve()
    return DEFAULT_SESSION_DIR / "session.json"


@dataclass
class AppSession:
    """A running (or last known) gallery process."""

    pid: int
    port: int
    exe: str
    log: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSession":
        missing = {"pid", "port", "exe", "log"} - data.keys()
        if missing:
            raise ValueError(f"session file is missing {sorted(missing)}")
        return cls(
            pid=int(data["pid"]),
            port=int(data["port"]),
            exe=str(data["exe"]),
            log=str(data["log"]),
            started_at=str(data.get("started_at", "")),
        )


def _locked_save_json(path: Path, data: Any) -> None:
    """Writes JSON with an exclusive lock, truncating only inside the lock."""
    try:
        handle = open(path, "r+", encoding="utf-8")
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "w", encoding="utf-8")
    with handle:
        unlock = _lock(handle)
        try:
            handle.seek(0)
            handle.truncate()
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
        finally:
            unlock()


def _lock(handle) -> Any:
    """Locks `handle` exclusively and returns the matching unlock function."""
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except ImportError:
        pass
    try:
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)

        def unlock() -> None:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

        return unlock
    except (ImportError, OSError):
        return lambda: None


class SessionStore:
    """Loads and saves the session file at `path`."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path).expanduser().resolve() if path else default_session_path()

    @property
    def directory(self) -> Path:
        return self.path.parent

    @property
    def log_path(self) -> Path:
        return self.directory / "story.log"

    @property
    def preview_root(self) -> Path:
        return self.directory / "previews"

    def load(self) -> Optional[AppSession]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        if not text.strip():
            return None
        data = json.loads(text)
        if not data:
            return None
        return AppSession.from_dict(data)

    def save(self, session: AppSession) -> None:
        _locked_save_json(self.path, session.to_dict())

    def clear(self) -> None:
        if self.path.exists():
            _locked_save_json(self.path, {})
