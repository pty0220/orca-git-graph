# Troubleshooting Orca Git Graph

## The Git Graph icon is missing

Enable the plugin system, add the **installed runtime plugin directory** under **Settings → Plugins → Development**, then use **Installed → Git Graph → Review and enable**. Look for a layers icon in the right sidebar or in its `…` overflow menu.

Adding the source checkout itself, or using the normal Git URL installer, is not the live-update installation path. Follow [the installation guide](installation.md).

## The panel does not follow project changes

Check that **Git Graph Sync** is still running. Restart it inside an Orca terminal:

```sh
python3 ~/.local/share/orca-git-graph/run.py watch
```

Run `doctor` and confirm the configured Orca profile. A switch normally takes the selection poll plus Git collection and Orca's Development reload. A large repository may take longer.

If you updated Orca after the installation, the configured state file can be out of date. Orca 1.4.214 and later store the workspace state in `profile-state.db` and stop updating `orca-data.json`. The sync process reads `profile-state.db` when it is next to the configured `orca-data.json`. To update `config.json` as well, stop Git Graph Sync, run `python3 install.py` again from the source checkout, and start the watcher. `doctor` shows the state file that the sync process reads.

If the installed HTML changes but Orca does not reload, verify that you registered the runtime path under **Development**, not a copied Local folder installation. Turn to another sidebar tab and back to test remounting. A newer Orca release may require an integration update.

## The panel shows a setup message or never updates

You likely registered the source `plugin` directory or a static installation copy. Run `python3 install.py` and register the exact absolute path printed by the installer. Keep the sync process running.

## The graph is blank or reports unavailable history

The selected folder may have no Git repository or no commits, or the process may not be allowed to read it. Confirm `git -C "/path/to/repository" log -1` from the same Orca terminal. Remote workspaces are not supported in this release.

On macOS, background LaunchAgents can lack Desktop/Documents access even when Orca can read those folders. This package deliberately starts the watcher in an Orca terminal, using the application's normal access. Do not solve this by exposing the graph over a public server.

## Multiple profiles were found

Pass `--profile NAME` or `--orca-state PATH` to the installer. It does not silently choose the most recently modified profile. If you switch Orca profiles later, reinstall with the correct profile and restart the watcher.

## Git Graph Sync is already running

Keep the existing sync terminal, or stop it with `Ctrl+C` before starting another one. The lock is released automatically when the process exits; do not delete the lock file to bypass a live process.

## The installer refuses the destination

Choose a new empty directory or the existing directory created by this installer. It will not replace an unrelated nonempty folder. Stop a running watcher before updating.

## Commits, branches, or file names seem missing

The default window is 400 commits, and branch filtering works only within that window. Increase `limit` in the installed `config.json` and restart, up to 2000. Remote refs are not fetched automatically. Changed files are capped at 200 per commit; merges may show none, and renames appear as separate additions and deletions.

## The graph is too narrow

Drag the left boundary of the right sidebar to widen it, or scroll the graph horizontally. This plugin is a sidebar tab adjacent to Source Control; it does not replace the built-in file-change list.

## Report a problem

Open a [GitHub issue](https://github.com/pty0220/orca-git-graph/issues/new/choose) with Orca version, OS, Python version, installation method, and reproduction steps. Include a redacted `doctor` result when useful. Do not attach `orca-data.json`, `profile-state.db`, runtime authentication files, private generated HTML, or unredacted screenshots of repository history.
