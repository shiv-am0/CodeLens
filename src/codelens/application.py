"""Local application boundary. Only explicit online GitHub capture uses a transport."""
from pathlib import Path
import os
import shutil
import sqlite3

from . import ingestion, persistence, records
from .domain import Locations, PolicyError


class Browser:
    def __init__(self, offline=False, locations=None):
        self.locations = locations or Locations.configured()
        self.offline = offline or os.environ.get("CODELENS_OFFLINE", "").lower() in {"1", "true", "yes"}

    def open(self, source, ref=None, parent=None):
        if "://" in source or source.startswith("git@"):
            canonical = ingestion.github_identity(source)
            if self.offline:
                raise PolicyError("Offline mode blocks GitHub capture. Resume a saved session.")
            capture = ingestion.remote_capture(canonical, ref)
        else:
            if ref is not None:
                raise ValueError("--ref applies to GitHub sources.")
            capture = ingestion.local_capture(Path(source).expanduser().resolve(), self.locations)
        with persistence.connect(self.locations) as db:
            return persistence.publish(db, capture, ref, parent)

    def refresh(self, sid):
        parent = self._read(persistence.session, sid)
        return self.open(parent["source"], parent["ref"], parent)

    def resume(self, sid):
        return self._session_read(records.resume, sid)

    def archive(self, sid):
        return self._session_read(records.saved, sid)

    def history(self, sid):
        return self._session_read(records.history, sid)

    def artifact(self, sid, section, version=None):
        return self._session_read(records.linked, sid, section, version)

    def _session_read(self, operation, sid, *args):
        with persistence.connect(self.locations) as db:
            persistence.session(db, sid)
            records.recover(db, self.locations, sid)
            with db:
                db.execute("BEGIN")
                return operation(db, sid, *args)

    def sessions(self, limit=50, offset=0):
        return self._read(persistence.sessions, limit, offset)

    def files(self, sid, limit=50, offset=0):
        return self._read(persistence.file_list, sid, limit, offset)

    def source(self, sid, path, start=1, end=None):
        return self._read(persistence.source, sid, path, start, end)

    def search(self, sid, query, limit=10):
        return self._read(persistence.search, sid, query, limit)

    def _read(self, operation, *args):
        with persistence.connect(self.locations) as db:
            return operation(db, *args)

    def doctor(self):
        with persistence.connect(self.locations) as db:
            return dict(database=str(self.locations.data / "codelens.sqlite3"),
                        config=str(self.locations.config), cache=str(self.locations.cache),
                        schema=db.execute("PRAGMA user_version").fetchone()[0],
                        journal=db.execute("PRAGMA journal_mode").fetchone()[0],
                        sqlite=sqlite3.sqlite_version, git=shutil.which("git"),
                        retrieval="fts5" if persistence.has_fts(db) and persistence.index_present(db)
                        else "bounded lexical scan", offline=self.offline)
