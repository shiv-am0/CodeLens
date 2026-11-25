"""Command adapter for the local repository browser."""
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Annotated

import typer

from .application import Browser
from .domain import GenerationError, Missing, PolicyError

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Capture and browse local repository snapshots.")
history = typer.Typer(no_args_is_help=True, help="Browse independent saved sessions.")
app.add_typer(history, name="sessions")
Json = Annotated[bool, typer.Option("--json", help="Write one JSON result.")]
Offline = Annotated[bool, typer.Option("--offline", help="Block network operations.")]
Limit = Annotated[int, typer.Option(min=1, max=100)]
Offset = Annotated[int, typer.Option(min=0)]


def printable(value):
    return "".join(ch if ch.isprintable() or ch in "\n\t" else ascii(ch)[1:-1] for ch in str(value))


def display(result, as_json):
    if as_json:
        typer.echo(json.dumps(result))
        return
    rows = result if isinstance(result, list) else [result]
    if not rows:
        typer.echo("No results.")
    for row in rows:
        if "text" in row:
            typer.echo(f"{printable(row['path'])}  lines {row['start']}–{row['end']}")
            typer.echo(printable(row["text"].replace("\r\n", "\n")))
        else:
            for key, value in row.items():
                if value is not None:
                    typer.echo(f"{key}: {printable(value)}")
            typer.echo()


@app.command("open")
def open_repository(source: str, ref: str | None = None, offline: Offline = False, json_output: Json = False):
    """Capture a directory or public GitHub repository and start a session."""
    display(Browser(offline).open(source, ref), json_output)


@app.command()
def refresh(session_id: str, offline: Offline = False, json_output: Json = False):
    """Capture the source again. Changed content starts a linked session."""
    display(Browser(offline).refresh(session_id), json_output)


@history.command("list")
def list_sessions(limit: Limit = 50, offset: Offset = 0, offline: Offline = False, json_output: Json = False):
    """List saved sessions, newest first."""
    display(Browser(offline).sessions(limit, offset), json_output)


@history.command()
def resume(session_id: str, offline: Offline = False, json_output: Json = False):
    """Reopen a session and report its saved identity."""
    data = Browser(offline).resume(session_id)
    if json_output:
        display(data, True)
        return
    artifacts = data.pop("artifacts", [])
    messages = data.pop("messages", [])
    display(data, False)
    for item in artifacts:
        typer.echo(f"{item['section']}  version {item['id']}  {item['status']}")
    for message in messages:
        typer.echo(f"\n{message['role']} ({message['status']})\n{printable(message['content'])}")


@app.command()
def files(session_id: str, limit: Limit = 50, offset: Offset = 0, offline: Offline = False, json_output: Json = False):
    """List paths and coverage from the saved snapshot."""
    display(Browser(offline).files(session_id, limit, offset), json_output)


@app.command()
def source(session_id: str, path: str, start: int = 1, end: int | None = None,
           offline: Offline = False, json_output: Json = False):
    """Read an inclusive range of stored source lines."""
    display(Browser(offline).source(session_id, path, start, end), json_output)


@app.command()
def search(session_id: str, query: str, limit: Limit = 10, offline: Offline = False, json_output: Json = False):
    """Find matching chunks in the session's snapshot."""
    display(Browser(offline).search(session_id, query, limit), json_output)


@app.command()
def doctor(offline: Offline = False, json_output: Json = False):
    """Check local paths, SQLite, search capability and Git."""
    display(Browser(offline).doctor(), json_output)


@app.command()
def setup(provider: str | None = None, model: str | None = None, endpoint: str | None = None,
          input_bytes: int = 12000, output_tokens: int = 2048, json_output: Json = False):
    """Save user settings. Supply the OpenAI key through OPENAI_API_KEY."""
    from .settings import configure
    if sys.stdin.isatty():
        provider = provider or typer.prompt("Provider (openai or ollama)")
        model = model or typer.prompt("Model ID")
    if not provider or not model:
        raise ValueError("Provide both --provider and --model for noninteractive setup.")
    display(configure(Browser().locations, provider, model, endpoint, input_bytes, output_tokens), json_output)


@app.command()
def analyze(session_id: str, section: str | None = None,
            all_sections: Annotated[bool, typer.Option("--all")] = False,
            regenerate: bool = False, offline: Offline = False, json_output: Json = False):
    """Generate one section or all eight. Rerun to reuse completed sections."""
    from .context import SECTIONS
    from .generation import Analysis
    if all_sections == bool(section):
        raise ValueError("Choose exactly one of --section NAME and --all.")
    if section and section not in SECTIONS:
        raise ValueError("Available sections: " + ", ".join(SECTIONS))
    service = Analysis(Browser(offline))
    results = []
    for name in (SECTIONS if all_sections else [section]):
        try:
            item = service.run(session_id, name, regenerate=regenerate)
        except KeyboardInterrupt:
            typer.echo("Cancelled. Completed sections and the current partial attempt are saved.", err=True)
            raise typer.Exit(130)
        summary = {k: item[k] for k in ("section", "id", "status", "cached")}
        results.append(summary)
        if not json_output:
            display(summary, False)
    if json_output:
        display(results, True)


@app.command()
def ask(session_id: str, question: str, request_id: str | None = None,
        offline: Offline = False, json_output: Json = False):
    """Stream a repository answer and persist both turns. Reuse a request ID for explicit replay."""
    from .generation import Analysis
    streamed = 0

    def emit(delta):
        nonlocal streamed
        streamed += len(delta)
        typer.echo(printable(delta), nl=False)
    try:
        result = Analysis(Browser(offline)).run(session_id, "chat", question, request_id=request_id,
                                                on_text=None if json_output else emit)
    except KeyboardInterrupt:
        typer.echo("\nCancelled. The partial turn is available in history.", err=True)
        raise typer.Exit(130)
    if json_output:
        display(result, True)
    else:
        typer.echo(printable(result["body"][streamed:]))


@app.command("history")
def conversation(session_id: str, offline: Offline = False, json_output: Json = False):
    """Read the saved dialogue, including partial answers, in conversation order."""
    display(Browser(offline).history(session_id), json_output)


def write_text(body):
    if sys.stdout.isatty():
        typer.echo(printable(body))
    else:
        sys.stdout.buffer.write(body.encode("utf-8"))


@app.command()
def show(session_id: str, section: str, version: int | None = None,
         offline: Offline = False, json_output: Json = False):
    """Read the last selected completed section, or inspect a specific version ID."""
    item = Browser(offline).artifact(session_id, section, version)
    if json_output:
        display(item, True)
    else:
        if item["status"] != "complete":
            typer.echo(f"Saved {item['status']} attempt {item['id']}: {item['error'] or ''}", err=True)
        write_text(item["body"])


@app.command("export")
def export_session(session_id: str, format: str = "markdown", output: Path | None = None,
                   offline: Offline = False):
    """Export saved text and source evidence. --output must name a new file."""
    from .records import render
    browser = Browser(offline)
    if format == "mermaid":
        diagram = browser.artifact(session_id, "diagram")
        if diagram["status"] != "complete":
            raise PolicyError("No completed diagram to export.")
        body = diagram["body"]
    else:
        body = render(browser.archive(session_id), format)
    if output is None:
        write_text(body)
    else:
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(dir=output.parent, delete=False) as tmp:
            name = Path(tmp.name)
        try:
            name.write_bytes(body.encode("utf-8"))
            os.link(name, output)
        finally:
            name.unlink(missing_ok=True)


def main():
    try:
        app()
    except (ValueError, Missing, PolicyError, GenerationError, sqlite3.Error, OSError) as exc:
        typer.echo(printable(exc), err=True)
        codes = {ValueError: 2, Missing: 3, PolicyError: 4}
        code = next((code for kind, code in codes.items() if isinstance(exc, kind)), 1)
        sys.exit(code)
