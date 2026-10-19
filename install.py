#!/usr/bin/env python3
"""Install a private runtime copy; no pip, Node.js, administrator access, or Orca config writes."""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from orca_git_graph.app import atomic_write, empty_repo, render_html
from orca_git_graph.workspace import WorkspaceError, discover_state

SOURCE = Path(__file__).resolve().parent


def find_orca():
    explicit = os.environ.get("ORCA_CLI_COMMAND")
    if explicit:
        return shutil.which(explicit) or (explicit if Path(explicit).is_file() else None)
    if sys.platform == "darwin":
        bundled = Path("/Applications/Orca.app/Contents/Resources/bin/orca")
        if bundled.is_file():
            return str(bundled)
    # Avoid the unrelated GNOME screen reader named `orca` on Linux.
    return shutil.which("orca-ide" if sys.platform.startswith("linux") else "orca")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, default=Path.home() / ".local/share/orca-git-graph")
    parser.add_argument("--orca-state", help="Explicit path to the active profile's profile-state.db or orca-data.json")
    parser.add_argument("--profile", help="Orca profile directory name, for example local-default")
    parser.add_argument("--no-start", action="store_true", help="Install files without opening a sync terminal")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 9):
        parser.error("Python 3.9 or later is required")
    if not shutil.which("git"):
        parser.error("Git was not found on PATH")
    try:
        state = discover_state(args.orca_state, args.profile)
    except WorkspaceError as error:
        parser.error(str(error))
    target = args.install_dir.expanduser().resolve()
    if target == SOURCE or SOURCE in target.parents:
        parser.error("Install outside the source checkout to keep generated Git data private")
    if target.exists() and any(target.iterdir()) and not (target / ".orca-git-graph-install").exists():
        parser.error("The destination is not an Orca Git Graph installation; choose an empty directory")
    target.mkdir(parents=True, exist_ok=True)
    marker = target / ".orca-git-graph-install"
    marker.write_text("orca-git-graph\n", encoding="utf-8")
    # Refuse updates while the existing sync process is reading these files.
    from orca_git_graph.app import watcher_lock
    try:
        with watcher_lock(target / ".watcher.lock"):
            shutil.copytree(SOURCE / "orca_git_graph", target / "orca_git_graph", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copy2(SOURCE / "run.py", target / "run.py")
            (target / "plugin").mkdir(exist_ok=True)
            shutil.copy2(SOURCE / "plugin/orca-plugin.json", target / "plugin/orca-plugin.json")
            config = dict(orca_state_path=str(state), limit=400, git_interval=10, selection_interval=0.75)
            if (target / "config.json").exists():
                old = json.loads((target / "config.json").read_text(encoding="utf-8"))
                config.update({k: old[k] for k in ("limit", "git_interval", "selection_interval") if k in old})
            atomic_write(target / "config.json", json.dumps(config, indent=2) + "\n")
            atomic_write(target / "plugin/panel.html", render_html(empty_repo(None, "Start Git Graph Sync to load your current workspace.")))
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    command = shlex.join([sys.executable, str(target / "run.py"), "watch"])
    print("\nInstalled Orca Git Graph.\n")
    print("One-time registration in Orca:")
    print("  1. Open Settings > Plugins and enable the plugin system.")
    print("  2. Expand Development > Add path and paste:")
    print("     " + str(target / "plugin"))
    print("  3. Select Installed > Git Graph > Review and enable.")
    print("  4. Click the layers icon (Git Graph) in the right sidebar.\n")
    print("Start or restart the sync process in an Orca terminal:")
    print("  " + command)
    started = False
    cli = find_orca()
    worktree = os.environ.get("ORCA_WORKTREE_ID")
    if not args.no_start and cli and worktree and sys.platform != "win32":
        result = subprocess.run([cli, "terminal", "create", "--worktree", "id:" + worktree.removeprefix("id:"),
                                 "--title", "Git Graph Sync", "--command", command, "--json"],
                                capture_output=True, text=True, timeout=20)
        try:
            started = result.returncode == 0 and json.loads(result.stdout).get("ok", False)
        except ValueError:
            pass
    if started:
        print("\nOpened a Git Graph Sync terminal. Keep it open for automatic updates.")
    else:
        print("\nRun the command above in an Orca terminal. Keep that terminal open.")
    print("The installer does not edit Orca settings or grant plugin permissions.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
