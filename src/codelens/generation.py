"""Serialize one session's generation while leaving SQLite available to readers."""
from contextlib import closing
from dataclasses import asdict
import time
from uuid import uuid4

from . import context, persistence, records, settings
from .domain import PolicyError


class Analysis:
    def __init__(self, browser):
        self.browser = browser

    def run(self, sid, section, question=None, regenerate=False, request_id=None, on_text=None):
        if section not in context.SECTIONS and section != "chat":
            raise ValueError("Choose a section: " + ", ".join(context.SECTIONS))
        if section == "chat" and (not question or not question.strip()):
            raise ValueError("Enter a question.")
        if request_id is not None and not 1 <= len(request_id) <= 128:
            raise ValueError("Request ID must be 1–128 characters.")
        with persistence.connect(self.browser.locations) as db:
            snapshot = persistence.session(db, sid)["snapshot_id"]
            with records.session_lock(self.browser.locations, sid) as acquired:
                if not acquired:
                    raise PolicyError("Generation in progress for this session. Retry after it finishes.")
                records.interrupted(db, sid)
                if request_id:
                    prior = db.execute("SELECT * FROM generation WHERE session_id=? AND request_id=?",
                                       (sid, request_id)).fetchone()
                    if prior:
                        if (prior["section"], prior["question"]) != (section, question):
                            raise ValueError("Request ID already belongs to a different request.")
                        if prior["status"] != "complete":
                            raise PolicyError(f"Saved attempt is {prior['status']}. Use a new request ID to retry.")
                        return dict(records.unpack(prior), cached=True)
                if self.browser.offline:
                    raise PolicyError("Offline mode blocks inference. Use show, history or export.")
                config = settings.load(self.browser.locations)
                history = []
                if section == "chat":
                    history = list(reversed(db.execute("""SELECT question,body FROM generation
                        WHERE session_id=? AND section='chat' AND status='complete' ORDER BY id DESC LIMIT 32""",
                                                       (sid,)).fetchall()))
                messages, evidence = context.request(db, snapshot, section, question, history, config.input_bytes)
                key = context.signature([snapshot, section, messages, evidence, asdict(config), context.PROMPT_VERSION])
                with persistence.writer(db):
                    if section != "chat" and not regenerate:
                        hit = db.execute("""SELECT * FROM generation WHERE cache_key=? AND status='complete'
                                          ORDER BY id DESC LIMIT 1""", (key,)).fetchone()
                        if hit:
                            db.execute("INSERT OR REPLACE INTO artifact_link VALUES(?,?)", (sid, hit["id"]))
                            return dict(records.unpack(hit), session_id=sid, cached=True)
                    gid = db.execute("""INSERT INTO generation(session_id,snapshot_id,section,question,
                        request_id,cache_key,settings,prompt_version,evidence,status,format)
                        VALUES(?,?,?,?,?,?,?,?,?,'running',?)""",
                        (sid, snapshot, section, question, request_id or uuid4().hex, key,
                         context.encode(asdict(config)), context.PROMPT_VERSION, context.encode(evidence),
                         "mermaid" if section == "diagram" else "markdown")).lastrowid
                    if section != "chat":
                        db.execute("INSERT INTO artifact_link VALUES(?,?)", (sid, gid))
                return self._generate(db, gid, config, messages, section, evidence, on_text)

    @staticmethod
    def _generate(db, gid, config, messages, section, evidence, on_text):
        from .providers import GenerationError, stream
        body = ""
        usage = None
        checkpoint = 0.0
        try:
            with closing(stream(config, messages)) as events:
                for event in events:
                    if event.usage is not None:
                        usage = context.encode(event.usage)
                    if event.text:
                        body += event.text
                        if len(body) > 2_000_000:
                            raise GenerationError("Response exceeded local output limit.")
                        if time.monotonic() >= checkpoint:
                            db.execute("UPDATE generation SET body=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                       (body, gid))
                            checkpoint = time.monotonic() + 0.25
                        if on_text:
                            on_text(event.text)
                    if event.done:
                        break
                else:
                    raise GenerationError("Stream ended without a completion event.")
            final = context.finish(body, section, evidence)
            db.execute("""UPDATE generation SET body=?,status='complete',usage=?,updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""", (final, usage, gid))
        except BaseException as exc:
            status = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
            error = str(exc) if isinstance(exc, (GenerationError, PolicyError)) else status
            db.execute("UPDATE generation SET body=?,status=?,error=?,usage=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='running'",
                       (body, status, error, usage, gid))
            raise
        return dict(records.unpack(db.execute("SELECT * FROM generation WHERE id=?", (gid,)).fetchone()), cached=False)
