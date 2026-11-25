import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from codelens import persistence
from codelens.application import Browser
from codelens.domain import Capture, File, Locations


@pytest.fixture
def workspace(tmp_path):
    guard = tmp_path / "guard"
    guard.mkdir()
    shutil.copyfile(Path(__file__).with_name("wire_fixture.py"), guard / "sitecustomize.py")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "routes.py").write_text('@router.get("/widgets")\ndef widgets(): return []\n')
    (repo / "migrations.sql").write_text("CREATE TABLE widgets(id INTEGER PRIMARY KEY);\n")
    (repo / "main.py").write_text("from services import start\nstart()\n")
    (repo / "README.md").write_text("Run python main.py\n")

    def cli(*args, code=0, env=None, raw=False):
        child = {"PATH": os.defpath, "PYTHONPATH": str(guard), "CALLS": str(tmp_path / "calls"),
                 "CODELENS_HOME": str(tmp_path / "home"), **(env or {})}
        result = subprocess.run([str(Path(sys.executable).with_name("codelens")), *args],
                                env=child, cwd=tmp_path, capture_output=True, timeout=20)
        assert result.returncode == code, (result.stdout, result.stderr)
        if code:
            return result.stderr
        return result.stdout if raw else json.loads(result.stdout)
    return repo, cli


def test_eight_sections_cache_chat_and_frozen_exports(workspace, tmp_path):
    repo, cli = workspace
    sid = cli("open", str(repo), "--json")["session_id"]
    other = cli("open", str(repo), "--json")["session_id"]
    cli("setup", "--provider", "openai", "--model", "chosen-model", "--json")
    auth = {"OPENAI_API_KEY": "fixture"}
    assert b"429" in cli("analyze", sid, "--all", env={**auth, "FAIL": "api"}, code=1)
    result = cli("analyze", sid, "--all", "--json", env=auth)
    assert len(result) == 8
    assert [r["section"] for r in result if r["cached"]] == ["overview", "architecture", "folders"]
    assert len((tmp_path / "calls").read_text().splitlines()) == 9
    saved = cli("show", sid, "api", "--json")
    assert saved["evidence"][0]["path"] == "routes.py" and '@router.get("/widgets")' in saved["evidence"][0]["text"]
    assert cli("show", sid, "database", "--json")["evidence"][0]["path"] == "migrations.sql"
    # Cross-session sharing is explicit, and works without a key on a cache hit.
    assert cli("analyze", other, "--section", "api", "--json")[0]["id"] == saved["id"]
    assert cli("history", other, "--json") == []
    version = cli("analyze", sid, "--section", "api", "--regenerate", "--json", env=auth)[0]["id"]
    assert version != saved["id"] and cli("show", sid, "api", "--version", str(saved["id"]), "--json") == saved
    answer = cli("ask", sid, "Which widgets route exists?", "--request-id", "turn1", "--json", env=auth)
    assert answer["usage"] == {"completion_tokens": 3}
    assert cli("ask", sid, "Which widgets route exists?", "--request-id", "turn1", "--offline", "--json")["cached"]
    cli("ask", sid, "Different question", "--request-id", "turn1", code=2)
    cli("ask", sid, "Which table supports that route?", "--json", env=auth)
    calls = [json.loads(line) for line in (tmp_path / "calls").read_text().splitlines()]
    assert len(calls) == 12
    assert [m["role"] for m in calls[-1]["messages"]] == ["system", "user", "assistant", "user"]
    commands = [("export", sid, "--format", fmt) for fmt in ("markdown", "json", "mermaid")]
    commands += [("show", sid, "api"), ("sessions", "resume", sid, "--json"), ("history", sid, "--json")]
    before = [cli(*cmd, raw=True) for cmd in commands]
    cli("setup", "--provider", "ollama", "--model", "another-model", "--json")
    switched = cli("analyze", other, "--section", "api", "--json")[0]
    assert not switched["cached"] and switched["id"] != saved["id"]
    assert cli("show", other, "api", "--version", str(saved["id"]), "--json")["session_id"] == other
    (repo / "routes.py").write_text("# revised route")
    fresh = cli("refresh", sid, "--json")
    assert fresh["snapshot_id"] != saved["snapshot_id"]
    cli("show", fresh["session_id"], "api", code=3)
    shutil.rmtree(repo)
    (tmp_path / "home/config/generation.json").unlink()
    guard = {"READ_ONLY": "1", "CODELENS_OFFLINE": "1"}
    assert before == [cli(*cmd, "--offline", env=guard, raw=True) for cmd in commands]
    archive = json.loads(before[1])
    assert [r["role"] for r in archive["messages"]] == ["user", "assistant"] * 2
    assert archive["exchanges"][0]["body"] == answer["body"]
    assert before[2].startswith(b"flowchart TD")
    assert len((tmp_path / "calls").read_text().splitlines()) == 13


def test_cancellation_crash_and_invalid_responses(workspace):
    repo, cli = workspace
    sid = cli("open", str(repo), "--json")["session_id"]
    cli("setup", "--provider", "ollama", "--model", "fixture-local", "--json")
    cli("ask", sid, "widgets?", env={"STOP_STREAM": "interrupt"}, code=130)
    messages = cli("history", sid, "--json")
    assert messages[-1]["status"] == "cancelled" and messages[-1]["content"] == "Observation "
    cli("analyze", sid, "--section", "api", env={"STOP_STREAM": "kill"}, code=77)
    partial = cli("show", sid, "api", "--offline", "--json")
    assert partial["status"] == "interrupted" and partial["body"] == "Observation "
    for mode in ("citation", "truncated"):
        cli("analyze", sid, "--section", "api", env={"FAIL": mode}, code=1)
        assert cli("show", sid, "api", "--json")["status"] == "failed"
    assert not cli("analyze", sid, "--section", "api", "--json")[0]["cached"]
    saved = cli("show", sid, "api", "--json")
    assert saved["usage"] == {"eval_count": 3}
    assert cli("show", sid, "api", "--version", str(partial["id"]), "--json") == partial
    assert b"Offline" in cli("ask", sid, "widgets?", "--offline", code=4)


def test_upgrade_real_v1_store(tmp_path):
    locations = Locations(tmp_path / "data", tmp_path / "config", tmp_path / "cache")
    locations.data.mkdir()
    path = locations.data / "codelens.sqlite3"
    with sqlite3.connect(path, isolation_level=None) as db:
        db.row_factory = sqlite3.Row
        for sql in persistence.SCHEMA:
            db.execute(sql)
        db.execute("PRAGMA user_version=1")
        record = persistence.publish(db, Capture("/original", "local", "", [File.capture("x", b"original")]), None)
    browser = Browser(offline=True, locations=locations)
    assert browser.resume(record["session_id"]) == record
    assert browser.source(record["session_id"], "x")["text"] == "original"
    with sqlite3.connect(path.with_suffix(".v1.bak")) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
        assert backup.execute("SELECT id FROM session").fetchone()[0] == record["session_id"]
    assert browser.doctor()["schema"] == 2


def test_generation_lock_and_budget(workspace, tmp_path):
    from codelens.context import encode, request
    from codelens.records import session_lock
    repo, cli = workspace
    opened = cli("open", str(repo), "--json")
    sid = opened["session_id"]
    home = tmp_path / "home"
    loc = Locations(home / "data", home / "config", home / "cache")
    cli("setup", "--provider", "ollama", "--model", "selected", "--json")
    with session_lock(loc, sid) as held:
        assert held
        assert b"in progress" in cli("ask", sid, "widgets?", code=4)
        assert cli("history", sid, "--offline", "--json") == []
    with persistence.connect(loc) as db:
        messages, evidence = request(db, opened["snapshot_id"], "chat", "widgets?",
                                     [("old", "a" * 6000), ("recent", "last completed answer")], 2048)
        assert len(encode(messages).encode()) <= 2048 and evidence
        assert [m["content"] for m in messages[1:-1]] == ["recent", "last completed answer"]
    cli("ask", sid, "widgets?", "--json")
    cli("export", sid, "--format", "json", "--output", str(tmp_path / "archive.json"), raw=True)
    assert json.loads((tmp_path / "archive.json").read_bytes())["exchanges"][0]["status"] == "complete"
    cli("export", sid, "--output", str(tmp_path / "archive.json"), code=1)
