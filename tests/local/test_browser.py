import concurrent.futures
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile

import pytest

from codelens import ingestion, persistence
from codelens.application import Browser
from codelens.domain import Locations, PolicyError


@pytest.fixture
def cli(tmp_path):
    # Every child process rejects network traffic, including loopback.
    guard = tmp_path / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import sys\ndef guard(event,args):\n"
        " if event in ('socket.connect','socket.getaddrinfo'): raise AssertionError('unexpected network')\n"
        "sys.addaudithook(guard)\n")
    env = {"PATH": os.defpath, "CODELENS_HOME": str(tmp_path / "home"),
           "PYTHONPATH": str(guard), "CODELENS_OFFLINE": "1"}

    def run(*args, code=0):
        result = subprocess.run([str(Path(sys.executable).with_name("codelens")), *args, "--json"],
                                cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
        assert result.returncode == code, result.stderr
        if code:
            assert not result.stdout
            return result.stderr
        return json.loads(result.stdout)
    return run


def test_installed_offline_lifecycle(cli, tmp_path):
    root = tmp_path / "work"
    root.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    git("init", "-q")
    body = "row\r\n" * 200 + "unique_marker"
    (root / "code.txt").write_bytes(body.encode())
    (root / "kept").mkdir()
    (root / "kept/tracked").write_text("tracked")
    git("add", ".")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
    (root / ".gitignore").write_text("kept/\nignored/\n")
    (root / "ignored").mkdir()
    (root / "ignored/file").write_text("skip")
    (root / "kept/untracked").write_text("skip")
    (root / "node_modules").mkdir()
    (root / "node_modules/noise").write_text("skip")
    (root / ".env").write_text("skip")
    (root / "link").symlink_to(tmp_path)
    (root / "empty").touch()
    (root / "untracked").write_text("new file")
    (root / "huge").write_bytes(b"x" * (ingestion.MAX_FILE + 1))
    (root / "binary").write_bytes(b"a\x00b")

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        a, b = list(pool.map(lambda _: cli("open", str(root)), range(2)))
    sid = a["session_id"]
    assert sid != b["session_id"] and a["snapshot_id"] == b["snapshot_id"]
    assert not cli("refresh", sid)["changed"]
    coverage = {r["path"]: r["coverage"] for r in cli("files", sid)}
    assert coverage == {"code.txt": "full", "untracked": "full", "empty": "full",
                        "huge": "oversize", "binary": "binary", "kept/tracked": "full"}
    assert cli("source", sid, "empty")["line_count"] == 0
    (root / "code.txt").write_text("updated")
    updated = cli("refresh", sid)
    assert updated["changed"] and updated["parent_session_id"] == sid
    assert updated["commit_sha"] == a["commit_sha"]
    (root / "untracked").write_text("changed untracked")
    again = cli("refresh", updated["session_id"])
    assert again["snapshot_id"] != updated["snapshot_id"]
    shutil.rmtree(root)
    assert cli("sessions", "resume", sid, "--offline") == a
    assert len(cli("sessions", "list")) == 4
    hit, = cli("search", sid, "unique_marker", "--offline")
    assert (hit["start"], hit["end"], hit["text"]) == (161, 201, "row\r\n"*40 + "unique_marker")
    assert cli("source", b["session_id"], "code.txt", "--start", "200")["text"] == "row\r\nunique_marker"
    assert cli("source", updated["session_id"], "code.txt")["text"] == "updated"
    assert cli("search", updated["session_id"], "unique_marker") == []
    assert "Offline" in cli("open", "https://github.com/test/repo", code=4)
    assert "secret-token" not in cli("open", "https://secret-token@github.com/test/repo", code=2)
    cli("source", sid, "../outside", code=3)
    cli("sessions", "resume", "absent", code=3)
    with sqlite3.connect(cli("doctor")["database"]) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("SELECT count(*) FROM snapshot").fetchone()[0] == 3


@pytest.fixture
def browser(tmp_path):
    return Browser(locations=Locations(*(tmp_path / n for n in ("data", "config", "cache"))))


def test_remote_commit_and_offline_refresh(browser, monkeypatch):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        entry = tarfile.TarInfo("repo-sha/sample.py")
        entry.size = 5
        tar.addfile(entry, io.BytesIO(b"hello"))
    calls = []
    sha = "a" * 40

    def transport(url, accept, limit):
        calls.append(url)
        return sha.encode() if "/commits/" in url else archive.getvalue()

    monkeypatch.setattr(ingestion, "download", transport)
    for ref in ("feature/one", sha, None):
        result = browser.open("https://github.com/Owner/Example.git", ref)
        assert result["commit_sha"] == sha
        assert calls[-1].endswith("/tarball/" + sha)
        assert browser.source(result["session_id"], "sample.py", 1, None)["text"] == "hello"
    assert calls[0].endswith("/commits/feature%2Fone")
    browser.offline = True
    with pytest.raises(PolicyError, match="Offline"):
        browser.refresh(result["session_id"])
    assert len(calls) == 6


def test_atomic_failure_and_fts_fallback(browser, tmp_path, monkeypatch):
    root = tmp_path / "work"
    root.mkdir()
    (root / "x").write_text("needle")
    monkeypatch.setattr(persistence, "has_fts", lambda db: False)
    with monkeypatch.context() as patch:
        def fail(*args):
            raise RuntimeError("interrupted")

        patch.setattr(persistence, "store_file", fail)
        with pytest.raises(RuntimeError, match="interrupted"):
            browser.open(str(root))
    with persistence.connect(browser.locations) as db:
        for table in ("repository", "snapshot", "file", "session"):
            assert db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    sid = browser.open(str(root))["session_id"]
    assert browser.search(sid, "needle", 1)[0]["start"] == 1
    assert browser.doctor()["retrieval"] == "bounded lexical scan"
    with persistence.connect(browser.locations) as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            browser.open(str(root))
        db.rollback()
        db.execute("PRAGMA user_version=99")
    with pytest.raises(PolicyError, match="newer"):
        browser.doctor()


def test_plain_directory_limits_and_home_exclusion(browser, tmp_path, monkeypatch):
    root = tmp_path
    (root / "one").write_text("a" * 9000 + "\nlast")
    # Create the store within the captured directory before the first capture.
    browser.doctor()
    sid = browser.open(str(root))["session_id"]
    assert [row["path"] for row in browser.files(sid)] == ["one"]
    assert browser.search(sid, "last")[0]["start"] == 2
    assert browser.source(sid, "one", 1, 1)["text"] == "a" * 9000 + "\n"
    monkeypatch.setattr(ingestion, "MAX_FILES", 1)
    (root / "two").touch()
    with pytest.raises(PolicyError, match="count limit"):
        browser.refresh(sid)
    assert len(browser.sessions()) == 1
