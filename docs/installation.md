# Install Orca Git Graph

Orca Git Graph adds an interactive Git history graph to the Orca desktop IDE's right sidebar. Setup has two parts: install the local sync tool, then register its panel in Orca once.

## 1. Check the requirements

- Orca desktop, tested on version 1.4.185 on macOS. The sync process also reads the `profile-state.db` workspace state of Orca 1.4.214 and later (checked with 1.4.224).
- Python 3.9 or later: `python3 --version`.
- Git: `git --version`.
- A local repository already opened in Orca.

No Node.js, npm, pip packages, GitHub token, administrator access, or network server is required at runtime. Downloading the source requires internet access. Windows/Linux desktop integration is experimental, even though the core code and installer are covered by automated tests.

## 2. Download and install

### Recommended: clone from an Orca terminal

```sh
git clone https://github.com/pty0220/orca-git-graph.git
cd orca-git-graph
python3 install.py
```

The installer copies the application into:

```text
~/.local/share/orca-git-graph/
```

It prints the full absolute plugin directory to paste into Orca. It also attempts to create a **Git Graph Sync** terminal in your current Orca workspace. If automatic terminal creation is unavailable, use the start command printed by the installer.

### Alternative: download a ZIP

1. Open [GitHub Releases](https://github.com/pty0220/orca-git-graph/releases).
2. Download the source ZIP for the desired version and extract it.
3. Open a terminal in the extracted folder.
4. Run `python3 install.py`.

You can also use GitHub's **Code → Download ZIP** for the current development version. Do not point Orca at the downloaded source's `plugin` directory: register the installed runtime path printed by the installer.

### Windows

From an Orca terminal with Python and Git installed:

```powershell
git clone https://github.com/pty0220/orca-git-graph.git
cd orca-git-graph
py -3 install.py --no-start
py -3 "$HOME\.local\share\orca-git-graph\run.py" watch
```

Automatic terminal creation is intentionally disabled on Windows. Follow the same Development registration steps below. End-to-end Orca desktop behavior on Windows has not yet been verified.

## 3. Register the live panel in Orca

1. Open **Settings → Plugins**.
2. Turn on **Plugin system**, if it is off.
3. Expand the **Development** section near the bottom.
4. Paste the **absolute plugin directory printed by the installer** into the development path field.
5. Click **Add path**.
6. Switch the plugin catalog to **Installed**.
7. Find **Git Graph** by publisher `pty0220`.
8. Choose **Review and enable**, then **Enable plugin**.
9. Return to your workspace.
10. Click the **layers icon** in the right-hand activity bar. Its tooltip is **Git Graph**. If it is hidden, open the `…` menu.

The manifest declares zero Orca API capabilities and no background plugin worker. The separate Python sync process still reads your configured Orca state file and selected local Git repository.

**Why Development mode?** This panel's HTML is regenerated as your project changes. Development mode reloads that live file. Orca's generic Git URL or Local folder installation copies a snapshot, so it is unsuitable for this release's live-update architecture.

## 4. Start the sync process

If **Git Graph Sync** is already running, leave it open. Otherwise run:

```sh
python3 ~/.local/share/orca-git-graph/run.py watch
```

Move between projects in Orca's left sidebar. The repository name, branch, HEAD, and graph should follow. The default selection poll is 0.75 seconds, followed by Git collection and Orca's panel reload. Small repositories usually switch within about 1–3 seconds.

Keep the sync terminal running. After quitting and reopening Orca, restart it with the same command. Running the watcher twice for the same installation is rejected by a process lock.

## Custom locations and multiple profiles

Choose an installation directory:

```sh
python3 install.py --install-dir "$HOME/tools/orca-git-graph" --no-start
```

Select a specific Orca profile:

```sh
python3 install.py --profile local-default
```

Or supply the exact state-file path:

```sh
python3 install.py --orca-state "/path/to/orca/profile/profile-state.db"
```

Use the path of `orca-data.json` for an Orca release that stores the state as JSON.

Default Orca data roots:

| Platform | Data root |
| --- | --- |
| macOS | `~/Library/Application Support/orca` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/orca` |
| Windows | `%APPDATA%\orca` |

`ORCA_USER_DATA_PATH`, when set, overrides the root. The installer searches profile directories for `profile-state.db` (Orca 1.4.214 and later) or `orca-data.json` (Orca 1.4.185). If a profile has both files, it uses `profile-state.db`. If multiple profiles exist, it asks for an explicit `--profile` or `--orca-state` argument rather than choosing one silently.

## Configuration

The installed `config.json` contains:

```json
{
  "orca_state_path": "/path/to/the/selected/profile/profile-state.db",
  "limit": 400,
  "git_interval": 10,
  "selection_interval": 0.75
}
```

Change the limit or intervals, then restart Git Graph Sync. `limit` must be 1–2000; intervals must be at least 0.2 seconds. Large histories take longer to collect and render. Runtime data remains outside the source checkout.

## Update

1. Stop Git Graph Sync with `Ctrl+C` in its terminal.
2. In the source checkout, run:

   ```sh
   git pull --ff-only
   python3 install.py
   ```

3. Keep the same Development path registered. If the plugin manifest changes, Orca may request another review.
4. Start Git Graph Sync if the installer did not start it.

The installer preserves your commit limit and polling intervals. It finds the state file again, so a run after an Orca update also changes `orca_state_path` to the new state format. If you originally used a custom profile or installation path, pass those flags again. It refuses to overwrite an unrecognized nonempty directory or update a running watcher.

## Uninstall

1. Stop the **Git Graph Sync** terminal.
2. In **Settings → Plugins → Development**, remove the installed plugin path.
3. Delete the `orca-git-graph` runtime directory you selected during installation.
4. Optionally delete the cloned source checkout.

No Git repository contents, Orca application files, startup services, or system settings are modified by the installer.

## Verify your installation

```sh
python3 ~/.local/share/orca-git-graph/run.py doctor
```

Check the reported state file, current selection, and plugin directory. See [Troubleshooting](troubleshooting.md) if the panel is missing, blank, or not following the project.
