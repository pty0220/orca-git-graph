"""Render the sandboxed panel and follow Orca workspace changes."""
import argparse
import contextlib
import datetime
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from .git_data import GitError, collect, fingerprint
from .workspace import current_state_file, discover_state, read_selection

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".panel-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def empty_repo(path, error):
    return dict(path=path or "", name=Path(path).name if path else "Select a workspace",
                commits=[], head=None, branch="", refs=[], upstream=None, ahead=0, behind=0, error=error)


def render_html(repo, limit=400, generated=None):
    data = dict(generated=generated or datetime.datetime.now().astimezone().isoformat(),
                limit=limit, repos=[repo], followWorkspace=True)
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return (PACKAGE / "panel.html").read_text(encoding="utf-8").replace("__GIT_GRAPH_DATA__", payload)


def publish(selection, config):
    path = selection.get("path")
    if path:
        try:
            repo = collect(path, config["limit"])
        except GitError:
            repo = empty_repo(path, "Git history is unavailable. Check folder access and whether this repository has commits.")
    else:
        repo = empty_repo(None, selection.get("error", "Select a Git workspace."))
    atomic_write(ROOT / "plugin/panel.html", render_html(repo, config["limit"]))
    print("Updated Git Graph: {} ({} commits)".format(repo["name"], len(repo["commits"])), flush=True)
    return repo


@contextlib.contextmanager
def watcher_lock(path):
    handle = open(path, "a+b")
    try:
        if sys.platform == "win32":
            import msvcrt
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        handle.close()
        raise RuntimeError("Git Graph Sync is already running for this installation.") from error
    try:
        yield
    finally:
        handle.close()


def load_config():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if not isinstance(config.get("limit"), int) or not 1 <= config["limit"] <= 2000:
        raise ValueError("limit must be an integer from 1 to 2000")
    for key in ("git_interval", "selection_interval"):
        if not isinstance(config.get(key), (int, float)) or config[key] < 0.2:
            raise ValueError(key + " must be at least 0.2 seconds")
    return config


def watch(config, once=False):
    previous_selection, previous_fingerprint = object(), object()
    next_git_check = 0.0
    while True:
        selection = read_selection(config["orca_state_path"])
        if selection != previous_selection or time.monotonic() >= next_git_check:
            try:
                git_state = fingerprint(selection["path"]) if selection.get("path") else None
            except GitError as error:
                git_state = ("unavailable", str(error))
            state = (selection, git_state)
            if state != previous_fingerprint:
                publish(selection, config)
                previous_fingerprint = state
            previous_selection = selection
            next_git_check = time.monotonic() + config["git_interval"]
        if once:
            return
        time.sleep(config["selection_interval"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Orca Git Graph: local Git history in Orca's right sidebar")
    parser.add_argument("command", choices=("watch", "build", "doctor"), nargs="?", default="watch")
    args = parser.parse_args(argv)
    try:
        config = load_config()
        if args.command == "doctor":
            from shutil import which
            print("Python: " + sys.version.split()[0])
            print("Git: " + (which("git") or "NOT FOUND"))
            print("Orca state: " + str(current_state_file(config["orca_state_path"])))
            print("Plugin folder: " + str(ROOT / "plugin"))
            selection = read_selection(config["orca_state_path"])
            print("Selection: " + (selection.get("path") or selection.get("error", "unknown")))
            print("Register the plugin folder under Settings > Plugins > Development.")
            return 0
        with watcher_lock(ROOT / ".watcher.lock"):
            watch(config, once=args.command == "build")
    except KeyboardInterrupt:
        print("Git Graph Sync stopped.")
    except (OSError, ValueError, RuntimeError) as error:
        print("Git Graph: " + str(error), file=sys.stderr)
        return 1
    return 0
