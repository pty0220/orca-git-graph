"""Isolate the experimental Orca state integration here.

Orca 1.4.185 keeps the state in orca-data.json. Orca 1.4.214 and later keep it in
profile-state.db, with one JSON document per former top-level key of orca-data.json. They
import orca-data.json once and never update it again, so that file becomes stale.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

STATE_FILES = ("profile-state.db", "orca-data.json")
MAX_STATE_SIZE = 16 * 1024 * 1024


class WorkspaceError(RuntimeError):
    pass


def data_root():
    override = os.environ.get("ORCA_USER_DATA_PATH")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/orca"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "orca"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "orca"


def profile_state(directory):
    return next((directory / name for name in STATE_FILES if (directory / name).is_file()), None)


def current_state_file(path):
    path = Path(path)
    database = path.with_name("profile-state.db")
    return database if path.name == "orca-data.json" and database.is_file() else path


def discover_state(explicit=None, profile=None):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise WorkspaceError("The supplied Orca state file does not exist.")
        return current_state_file(path)
    root = data_root()
    if profile:
        if Path(profile).name != profile or profile in (".", ".."):
            raise WorkspaceError("Profile must be a directory name, not a path.")
        state = profile_state(root / "profiles" / profile)
        if not state:
            raise WorkspaceError("The selected Orca profile has no state file.")
        return state.resolve()
    profiles = sorted(path for path in (root / "profiles").glob("*") if path.is_dir())
    candidates = [state for state in map(profile_state, profiles) if state]
    if (root / "orca-data.json").is_file():
        candidates.append(root / "orca-data.json")
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise WorkspaceError("Orca state was not found. Open Orca, or pass --orca-state PATH.")
    raise WorkspaceError("Multiple Orca profiles found. Choose --profile NAME or --orca-state PATH.")


def resolve_workspace(state):
    session = state.get("workspaceSession") or {}
    host = session.get("activeWorkspaceExecutionHostId")
    if host and host != "local":
        return {"error": "Remote workspaces are not supported in this release.", "key": host}
    # Orca runtime uses activeWorktreeId. activeWorkspaceKey may be stale after navigation.
    active = session.get("activeWorktreeId")
    if "activeWorktreeId" not in session:
        active = session.get("activeWorkspaceKey")
    if not isinstance(active, str) or not active:
        return {"error": "Select a Git workspace in Orca's left sidebar.", "key": None}
    key = active
    if active.startswith("worktree:"):
        active = active[len("worktree:"):]
    if active.startswith("folder:"):
        folder_id = active[len("folder:"):]
        folder = next((f for f in state.get("folderWorkspaces", []) if f.get("id") == folder_id), None)
        path = folder.get("path") if folder else None
    elif "::" in active:
        repo_id, path = active.split("::", 1)
        repo = next((r for r in state.get("repos", []) if r.get("id") == repo_id), None)
        if not repo or repo.get("kind", "git") not in ("git", "folder", "local"):
            return {"error": "The selected local repository is unavailable.", "key": key}
    else:
        path = None
    if not isinstance(path, str) or not Path(path).is_absolute():
        return {"error": "The selected workspace has no local folder.", "key": key}
    return {"path": path, "key": key}


def load_state_database(path):
    # mode=ro cannot change Orca's database, and a WAL reader does not block Orca's writes.
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        rows = connection.execute(
            "SELECT domain, CASE WHEN length(payload) <= ? THEN payload END FROM profile_state_documents"
            " WHERE domain IN ('workspaceSession', 'repos', 'folderWorkspaces')", (MAX_STATE_SIZE,)).fetchall()
    finally:
        connection.close()
    if any(payload is None for _, payload in rows):
        raise ValueError("State document is too large")
    return {domain: json.loads(payload) for domain, payload in rows}


def load_state(state_path):
    path = current_state_file(state_path)
    if path.suffix == ".db":
        return load_state_database(path)
    with path.open(encoding="utf-8") as source:
        # Bound malformed or unexpected files. Never print or copy the state document.
        raw = source.read(MAX_STATE_SIZE + 1)
    if len(raw) > MAX_STATE_SIZE:
        raise ValueError("State document is too large")
    return json.loads(raw)


def read_selection(state_path):
    try:
        return resolve_workspace(load_state(state_path))
    except (OSError, ValueError, AttributeError, TypeError, sqlite3.Error):
        return {"error": "Cannot read Orca's current workspace. Check the state-file setting.", "key": None}
