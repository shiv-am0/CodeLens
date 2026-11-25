"""SQLite schema v1. Publish a capture and its session with one commit."""
from contextlib import contextmanager
import hashlib
import os
import sqlite3
import time
from tempfile import NamedTemporaryFile
from pathlib import Path
from contextlib import closing

from .records import DDL
from uuid import uuid4

from .domain import POLICY, Missing, PolicyError
from .retrieval import chunks, expression, lines

SCHEMA = (
    "CREATE TABLE repository(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL UNIQUE)",
    """CREATE TABLE snapshot(id TEXT PRIMARY KEY, repository_id INTEGER NOT NULL REFERENCES repository,
       revision TEXT NOT NULL, manifest TEXT NOT NULL, policy TEXT NOT NULL,
       created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(repository_id,revision,manifest,policy))""",
    "CREATE TABLE blob(hash TEXT PRIMARY KEY, content BLOB NOT NULL)",
    """CREATE TABLE file(id INTEGER PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshot,
       path TEXT NOT NULL, size INTEGER NOT NULL, coverage TEXT NOT NULL, digest TEXT,
       blob_hash TEXT REFERENCES blob, line_count INTEGER NOT NULL, UNIQUE(snapshot_id,path))""",
    """CREATE TABLE chunk(id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL REFERENCES file,
       ordinal INTEGER NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL,
       text TEXT NOT NULL, hash TEXT NOT NULL, UNIQUE(file_id,ordinal))""",
    """CREATE TABLE session(id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshot,
       ref TEXT, parent TEXT REFERENCES session, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    "CREATE INDEX session_chronology ON session(created_at,id)",
)

SESSION = """SELECT session.id session_id, session.snapshot_id, session.parent parent_session_id,
    session.created_at, repository.id repository_id, repository.source, repository.kind,
    NULLIF(snapshot.revision,'') commit_sha, session.ref, snapshot.manifest
    FROM session JOIN snapshot ON session.snapshot_id=snapshot.id
    JOIN repository ON repository.id=snapshot.repository_id"""


def has_fts(db):
    try:
        db.execute("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(text)")
        db.execute("DROP TABLE temp.fts_probe")
        return True
    except sqlite3.OperationalError as exc:
        if "no such module" in str(exc):
            return False
        raise


@contextmanager
def writer(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


@contextmanager
def connect(locations):
    locations.data.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = locations.data / "codelens.sqlite3"
    os.close(os.open(path, os.O_CREAT | os.O_RDONLY, 0o600))
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 2:
            raise PolicyError("Store requires a newer CodeLens. Upgrade before opening it.")
        if version == 0:
            # A racing journal-mode change can return SQLITE_BUSY immediately,
            # even when the connection has a busy timeout.
            deadline = time.monotonic() + 5
            while True:
                try:
                    db.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError as exc:
                    if exc.sqlite_errorcode != sqlite3.SQLITE_BUSY or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
            with writer(db):
                if db.execute("PRAGMA user_version").fetchone()[0] == 0:
                    for statement in SCHEMA:
                        db.execute(statement)
                    if has_fts(db):
                        db.execute("CREATE VIRTUAL TABLE chunk_search USING fts5(path,text)")
                    for statement in DDL:
                        db.execute(statement)
                    db.execute("PRAGMA user_version=2")
        elif version == 1:
            with writer(db):
                if db.execute("PRAGMA user_version").fetchone()[0] == 1:
                    # A separate reader backs up the committed v1 image while this writer
                    # prevents competing migrations. Publish the backup before upgrading.
                    with NamedTemporaryFile(dir=locations.data, delete=False) as tmp:
                        backup = Path(tmp.name)
                    try:
                        with closing(sqlite3.connect(path)) as reader, closing(sqlite3.connect(backup)) as dest:
                            reader.backup(dest)
                            if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                                raise PolicyError("Schema backup failed integrity verification.")
                        backup.replace(path.with_suffix(".v1.bak"))
                    finally:
                        backup.unlink(missing_ok=True)
                    for statement in DDL:
                        db.execute(statement)
                    db.execute("PRAGMA user_version=2")
        yield db
    finally:
        db.close()


def session(db, sid):
    row = db.execute(SESSION + " WHERE session.id=?", (sid,)).fetchone()
    if row is None:
        raise Missing("Session not found.")
    return dict(row)


def sessions(db, limit, offset):
    return [dict(row) for row in db.execute(
        SESSION + " ORDER BY session.created_at DESC,session.rowid DESC LIMIT ? OFFSET ?", (limit, offset))]


def file_list(db, sid, limit, offset):
    snap = session(db, sid)["snapshot_id"]
    return [dict(row) for row in db.execute(
        "SELECT path,size,coverage,line_count FROM file WHERE snapshot_id=? ORDER BY path LIMIT ? OFFSET ?",
        (snap, limit, offset))]


def index_present(db):
    return bool(db.execute("SELECT 1 FROM sqlite_schema WHERE name='chunk_search'").fetchone())


def store_file(db, snapshot, f, indexed):
    rows = []
    blob_hash = None
    if f.data is not None:
        blob_hash = f.digest
        db.execute("INSERT OR IGNORE INTO blob VALUES(?,?)", (blob_hash, f.data))
        rows = lines(f.data.decode("utf-8"))
    fid = db.execute("""INSERT INTO file(snapshot_id,path,size,coverage,digest,blob_hash,line_count)
                     VALUES(?,?,?,?,?,?,?)""",
                     (snapshot, f.path, f.size, f.coverage, f.digest, blob_hash, len(rows))).lastrowid
    for ordinal, (start, end, passage) in enumerate(chunks(rows)):
        digest = hashlib.sha256(passage.encode()).hexdigest()
        cid = db.execute("""INSERT INTO chunk(file_id,ordinal,start,end,text,hash)
                         VALUES(?,?,?,?,?,?)""", (fid, ordinal, start, end, passage, digest)).lastrowid
        if indexed:
            db.execute("INSERT INTO chunk_search(rowid,path,text) VALUES(?,?,?)", (cid, f.path, passage))


def publish(db, capture, ref, parent=None):
    manifest = capture.manifest()
    with writer(db):
        db.execute("INSERT OR IGNORE INTO repository(kind,source) VALUES(?,?)", (capture.kind, capture.source))
        rid = db.execute("SELECT id FROM repository WHERE source=?", (capture.source,)).fetchone()[0]
        identity = (rid, capture.commit, manifest, POLICY)
        row = db.execute("""SELECT id FROM snapshot WHERE repository_id=? AND revision=?
                         AND manifest=? AND policy=?""", identity).fetchone()
        if row:
            snapshot = row[0]
        else:
            snapshot = uuid4().hex
            db.execute("INSERT INTO snapshot(id,repository_id,revision,manifest,policy) VALUES(?,?,?,?,?)",
                       (snapshot, *identity))
            indexed = index_present(db)
            for f in capture.files:
                store_file(db, snapshot, f, indexed)
        unchanged = parent is not None and parent["snapshot_id"] == snapshot
        if unchanged:
            sid = parent["session_id"]
        else:
            sid = uuid4().hex
            db.execute("INSERT INTO session(id,snapshot_id,ref,parent) VALUES(?,?,?,?)",
                       (sid, snapshot, ref, parent["session_id"] if parent else None))
    result = session(db, sid)
    if parent:
        result.update(changed=not unchanged, previous_session_id=parent["session_id"],
                      previous_snapshot_id=parent["snapshot_id"])
    return result


def source(db, sid, path, start, end):
    snap = session(db, sid)["snapshot_id"]
    row = db.execute("""SELECT file.coverage,blob.content FROM file LEFT JOIN blob ON blob.hash=file.blob_hash
                     WHERE snapshot_id=? AND path=?""", (snap, path)).fetchone()
    if row is None:
        raise Missing("Path does not exist in the selected snapshot.")
    if row["coverage"] != "full":
        raise PolicyError("File was excluded from text capture: " + row["coverage"])
    rows = lines(row["content"].decode())
    if start < 1 or start > max(1, len(rows)) or (end is not None and end < start):
        raise ValueError("Invalid inclusive line range.")
    end = min(end if end is not None else start + 199, len(rows))
    if end - start >= 200:
        raise ValueError("Read at most 200 lines per call.")
    return dict(snapshot_id=snap, path=path, start=start if rows else 0, end=end,
                line_count=len(rows), text="".join(rows[start-1:end]))


def search(db, sid, query, limit):
    snap = session(db, sid)["snapshot_id"]
    match = expression(query)
    if index_present(db) and has_fts(db):
        result = db.execute("""SELECT chunk.id chunk_id,file.path,start,end,chunk.text FROM chunk_search
            JOIN chunk ON chunk.id=chunk_search.rowid JOIN file ON file.id=chunk.file_id
            WHERE chunk_search MATCH ? AND snapshot_id=?
            ORDER BY bm25(chunk_search),chunk.id LIMIT ?""",
                            (match, snap, limit))
        return [dict(row, snapshot_id=snap) for row in result]
    # The capture limits bound this scan. Exact source reads use the same persistent files.
    tokens = [term.strip('"').casefold() for term in match.split(" AND ")]
    hits = []
    for row in db.execute("""SELECT chunk.id chunk_id,path,start,end,text FROM chunk
                          JOIN file ON file.id=chunk.file_id WHERE snapshot_id=? ORDER BY path,start""", (snap,)):
        text = (row["path"] + " " + row["text"]).casefold()
        if all(token in text for token in tokens):
            hits.append(dict(row, snapshot_id=snap))
            if len(hits) == limit:
                break
    return hits
