import copy
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from orca_git_graph.app import empty_repo, render_html, watcher_lock
from orca_git_graph.git_data import collect
from orca_git_graph.workspace import discover_state, read_selection, resolve_workspace, WorkspaceError

READ_ERROR = {"error": "Cannot read Orca's current workspace. Check the state-file setting.", "key": None}


def write_state_database(path, documents):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE profile_state_documents (domain TEXT PRIMARY KEY NOT NULL,"
                           " payload TEXT NOT NULL, domain_version INTEGER NOT NULL, revision INTEGER NOT NULL,"
                           " updated_at INTEGER NOT NULL, content_hash TEXT NOT NULL)")
        connection.executemany("INSERT INTO profile_state_documents VALUES (?, ?, 1, 1, 0, '')",
                               [(domain, json.dumps(value)) for domain, value in documents.items()])
        connection.commit()


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.path = str(Path(tempfile.gettempdir()) / "feature worktree")
        self.state = {"repos": [{"id": "repo", "kind": "git"}], "workspaceSession": {
            "activeWorktreeId": "repo::" + self.path, "activeWorkspaceKey": "worktree:stale::/stale"}}

    def test_active_id_overrides_stale_workspace_key(self):
        self.assertEqual(resolve_workspace(self.state)["path"], self.path)

    def test_worktree_switch_in_same_repository(self):
        path = str(Path(tempfile.gettempdir()) / "another worktree")
        self.state["workspaceSession"]["activeWorktreeId"] = "repo::" + path
        self.assertEqual(resolve_workspace(self.state)["path"], path)

    def test_deselection_does_not_restore_stale_workspace(self):
        self.state["workspaceSession"]["activeWorktreeId"] = None
        self.assertNotIn("path", resolve_workspace(self.state))

    def test_remote_does_not_read_a_matching_local_path(self):
        self.state["workspaceSession"]["activeWorkspaceExecutionHostId"] = "ssh:example"
        self.assertNotIn("path", resolve_workspace(self.state))

    def test_folder(self):
        self.state["workspaceSession"]["activeWorktreeId"] = "folder:notes"
        self.state["folderWorkspaces"] = [{"id": "notes", "path": self.path}]
        self.assertEqual(resolve_workspace(self.state)["path"], self.path)

    def test_removed_repo(self):
        self.state["repos"] = []
        self.assertNotIn("path", resolve_workspace(self.state))

    def test_multiple_profiles_require_explicit_choice(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("personal", "work"):
                path = Path(root) / "profiles" / name / "orca-data.json"
                path.parent.mkdir(parents=True)
                path.write_text("{}")
            with patch.dict(os.environ, {"ORCA_USER_DATA_PATH": root}):
                with self.assertRaises(WorkspaceError):
                    discover_state()
                self.assertEqual(discover_state(profile="work").parent.name, "work")

    def test_profile_state_database_is_preferred_over_json(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "profiles" / "local-default"
            profile.mkdir(parents=True)
            (profile / "orca-data.json").write_text("{}")
            (profile / "profile-state.db").write_bytes(b"")
            with patch.dict(os.environ, {"ORCA_USER_DATA_PATH": root}):
                self.assertEqual(discover_state().name, "profile-state.db")
                self.assertEqual(discover_state(profile="local-default").name, "profile-state.db")

    def test_stale_json_next_to_a_database_is_not_read(self):
        stale = copy.deepcopy(self.state)
        stale["workspaceSession"]["activeWorktreeId"] = "repo::" + str(Path(tempfile.gettempdir()) / "old worktree")
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "profiles" / "local-default"
            write_state_database(profile / "profile-state.db", self.state)
            (profile / "orca-data.json").write_text(json.dumps(stale))
            self.assertEqual(read_selection(profile / "orca-data.json")["path"], self.path)
            self.assertEqual(discover_state(profile / "orca-data.json").name, "profile-state.db")

    def test_mixed_profile_formats_require_explicit_choice(self):
        with tempfile.TemporaryDirectory() as root:
            for name, state in (("personal", "orca-data.json"), ("work", "profile-state.db")):
                path = Path(root) / "profiles" / name / state
                path.parent.mkdir(parents=True)
                path.write_bytes(b"")
            with patch.dict(os.environ, {"ORCA_USER_DATA_PATH": root}):
                with self.assertRaisesRegex(WorkspaceError, "Multiple Orca profiles found"):
                    discover_state()
                self.assertEqual(discover_state(profile="personal").name, "orca-data.json")
                with self.assertRaisesRegex(WorkspaceError, "has no state file"):
                    discover_state(profile="missing")

    def test_profile_state_database_worktree(self):
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "Application Support" / "profile-state.db"
            write_state_database(database, self.state)
            self.assertEqual(read_selection(database), {"path": self.path, "key": "repo::" + self.path})

    def test_profile_state_database_folder(self):
        self.state["workspaceSession"]["activeWorktreeId"] = "folder:notes"
        self.state["folderWorkspaces"] = [{"id": "notes", "path": self.path}]
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "profile-state.db"
            write_state_database(database, self.state)
            self.assertEqual(read_selection(database), {"path": self.path, "key": "folder:notes"})

    def test_profile_state_database_reads_committed_state_during_a_write(self):
        other = str(Path(tempfile.gettempdir()) / "another worktree")
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "profile-state.db"
            write_state_database(database, self.state)
            with closing(sqlite3.connect(database)) as orca:
                orca.execute("BEGIN IMMEDIATE")
                orca.execute("UPDATE profile_state_documents SET payload = ? WHERE domain = 'workspaceSession'",
                             (json.dumps({"activeWorktreeId": "repo::" + other}),))
                self.assertEqual(read_selection(database)["path"], self.path)
                orca.commit()
                self.assertEqual(read_selection(database)["path"], other)

    def test_profile_state_database_is_not_changed(self):
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "profile-state.db"
            write_state_database(database, self.state)
            before = database.read_bytes()
            read_selection(database)
            self.assertEqual(database.read_bytes(), before)

    def test_unreadable_profile_state_database(self):
        with tempfile.TemporaryDirectory() as root:
            other_schema = Path(root) / "other-schema" / "profile-state.db"
            other_schema.parent.mkdir()
            with closing(sqlite3.connect(other_schema)) as connection:
                connection.execute("CREATE TABLE unrelated (id INTEGER)")
                connection.commit()
            not_sqlite = Path(root) / "not-sqlite" / "profile-state.db"
            not_sqlite.parent.mkdir()
            not_sqlite.write_text("This is not a database.")
            missing = Path(root) / "missing" / "profile-state.db"
            for database in (other_schema, not_sqlite, missing):
                with self.subTest(database.parent.name):
                    self.assertEqual(read_selection(database), READ_ERROR)

    def test_oversized_profile_state_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "profile-state.db"
            write_state_database(database, self.state)
            with patch("orca_git_graph.workspace.MAX_STATE_SIZE", 10):
                self.assertEqual(read_selection(database), READ_ERROR)


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Example Developer")
        self.git("config", "user.email", "developer@example.com")
        self.commit("Initial commit", "base.txt")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=" + str(self.path / "no-hooks"),
                                        "-C", str(self.path), *args], stderr=subprocess.DEVNULL).decode().strip()

    def commit(self, message, name):
        (self.path / name).write_text(message, encoding="utf-8")
        self.git("add", "--", name)
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")

    def test_merge_tags_files_and_multiline_message(self):
        self.git("checkout", "-b", "feature/search")
        feature = self.commit("Add search\n\nA message with <script> and a separator \x1f.", "space name.txt")
        self.git("tag", "-a", "v0.1.0", "-m", "Example release")
        self.git("checkout", "main")
        self.commit("Add docs", "guide.md")
        self.git("merge", "--no-ff", "feature/search", "-m", "Merge search")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        repo = collect(self.path)
        lookup = {c["hash"]: c for c in repo["commits"]}
        self.assertEqual(len(lookup[repo["head"]]["parents"]), 2)
        self.assertIn("separator \x1f", lookup[feature]["message"])
        self.assertIn({"status": "A", "path": "space name.txt"}, lookup[feature]["files"])
        self.assertIn({"name": "feature/search", "type": "branch"}, lookup[feature]["refs"])
        self.assertIn({"name": "v0.1.0", "type": "tag"}, lookup[feature]["refs"])
        self.assertIn({"name": "origin/main", "type": "remote"}, lookup[repo["head"]]["refs"])

    @unittest.skipIf(os.name == "nt", "Windows does not support newline filenames")
    def test_newline_and_hash_shaped_filenames(self):
        name = "line\nbreak.txt"
        sha = self.commit("Add an unusual path", name)
        self.commit("Add a hash-shaped filename", sha)
        commits = collect(self.path)["commits"]
        self.assertIn({"status": "A", "path": sha}, commits[0]["files"])
        self.assertIn({"status": "A", "path": name}, commits[1]["files"])

    def test_detached_unreferenced_head_is_included(self):
        self.git("checkout", "--detach")
        sha = self.commit("Detached change", "detached.txt")
        repo = collect(self.path)
        self.assertEqual(repo["head"], sha)
        self.assertTrue(any(c["hash"] == sha for c in repo["commits"]))
        self.assertEqual(repo["branch"], "Detached HEAD")

    def test_ambient_git_dir_does_not_redirect_collection(self):
        with patch.dict(os.environ, {"GIT_DIR": "/nonexistent"}):
            self.assertEqual(collect(self.path)["name"], self.path.name)

    def test_html_script_termination_is_escaped(self):
        repo = collect(self.path)
        repo["commits"][0]["subject"] = "</script><script>window.bad=true</script>"
        page = render_html(repo)
        self.assertNotIn("</script><script>window.bad", page)
        self.assertIn("\\u003c/script>", page)

    def test_collection_does_not_change_git_state(self):
        before = self.git("status", "--porcelain"), self.git("show-ref"), self.git("rev-parse", "HEAD")
        collect(self.path)
        after = self.git("status", "--porcelain"), self.git("show-ref"), self.git("rev-parse", "HEAD")
        self.assertEqual(before, after)


class InstallationTests(unittest.TestCase):
    def test_clean_install_and_build_outside_checkout(self):
        import install
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "runtime with spaces"
            state = Path(root) / "orca-data.json"
            state.write_text('{"workspaceSession": {"activeWorktreeId": null}}')
            self.assertEqual(install.main(["--no-start", "--install-dir", str(dest), "--orca-state", str(state)]), 0)
            result = subprocess.run([os.sys.executable, str(dest / "run.py"), "build"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Select a Git workspace", (dest / "plugin/panel.html").read_text())
            with watcher_lock(dest / ".watcher.lock"):
                duplicate = subprocess.run([os.sys.executable, str(dest / "run.py"), "watch"], capture_output=True, text=True)
                self.assertNotEqual(duplicate.returncode, 0)
                self.assertIn("already running", duplicate.stderr)

    def test_build_follows_a_profile_state_database(self):
        import install
        with tempfile.TemporaryDirectory() as root:
            repository = Path(root) / "example project"
            repository.mkdir()
            for args in (["init", "-b", "main"],
                         ["-c", "user.name=Example Developer", "-c", "user.email=developer@example.com",
                          "commit", "--allow-empty", "-m", "Initial commit"]):
                subprocess.run(["git", "-c", "core.hooksPath=" + str(repository / "no-hooks"),
                                "-C", str(repository), *args], check=True, capture_output=True)
            database = Path(root) / "profile" / "profile-state.db"
            write_state_database(database, {"repos": [{"id": "repo", "kind": "git"}],
                                            "workspaceSession": {"activeWorktreeId": "repo::" + str(repository)}})
            dest = Path(root) / "runtime"
            self.assertEqual(install.main(["--no-start", "--install-dir", str(dest), "--orca-state", str(database)]), 0)
            result = subprocess.run([os.sys.executable, str(dest / "run.py"), "build"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Updated Git Graph: example project (1 commits)", result.stdout)
            self.assertIn("Initial commit", (dest / "plugin/panel.html").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
