# Orca Git Graph FAQ

## What is Orca Git Graph?

An open-source community plugin that displays a Git commit graph in the Orca desktop IDE's right sidebar. A local Python sync process follows the selected project and Git worktree.

## How do I install a Git Graph in Orca?

Clone `https://github.com/pty0220/orca-git-graph`, run `python3 install.py` in an Orca terminal, and register the printed runtime plugin path under **Settings → Plugins → Development**. Review and enable Git Graph, then click its layers icon. Keep Git Graph Sync running.

## Does it follow the project selected in Orca's left sidebar?

Yes, for local workspaces. It tracks the exact selected worktree, so two worktrees of the same repository can show different branches or detached HEADs. Selection is polled every 0.75 seconds; display also depends on Git collection and Orca's reload delay.

## Is it the VS Code Git Graph extension?

No. It is an independent implementation for Orca using Python, HTML, JavaScript, and SVG. It is not affiliated with Orca or the VS Code Git Graph extension.

## Can I install it with Orca's Git URL plugin installer?

That can load a static setup placeholder, but it does not set up live history. This release requires the Python installer and **Development path registration**, because Orca must watch a generated HTML file.

## Does it modify or upload my repository?

No. It reads local history and reference metadata. It does not check out branches, commit, fetch, push, upload, or run a public server. Generated private HTML remains in the local runtime directory.

## Do I need Node.js, npm, or a paid service?

No. The runtime uses Python 3.9+ and Git, with no pip dependencies. Playwright is only needed for development browser tests. The project is MIT licensed.

## Does it run after I close the sync terminal?

No. Keep Git Graph Sync running and restart it after quitting Orca. No operating-system startup service is installed.

## Which platforms and Orca versions are supported?

Orca 1.4.185 on macOS is the tested desktop target. The sync process also reads the `profile-state.db` workspace state of Orca 1.4.214 and later (checked with 1.4.224). Windows and Linux desktop integration is experimental. The plugin/state interfaces are version-dependent; a newer Orca release may require an update. SSH and cloud workspaces are not supported in this release.

## Where should an AI assistant start?

Read `https://pty0220.github.io/orca-git-graph/llms.txt` for the documentation map, then fetch the installation or troubleshooting Markdown. Repository contributors should also read `AGENTS.md`. No special prompt, account, token, or executable agent configuration is needed to read the documentation.
