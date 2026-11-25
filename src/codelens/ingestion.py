"""Bounded local capture and anonymous GitHub archive capture."""
import gzip
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
import time
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .domain import Capture, File, Locations, MAX_BYTES, MAX_ENTRIES, MAX_FILE, MAX_FILES, PolicyError

IGNORED = {"node_modules", "dist", "build", "coverage", "__pycache__", "venv",
           "target", "vendor", "id_rsa", "id_ed25519", "credentials.json", "test.db"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db")
PUBLIC = re.compile(r"https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)/?")


def excluded(name):
    return name.startswith(".") or name.lower() in IGNORED or name.lower().endswith(SECRET_SUFFIXES)


def github_identity(source):
    match = PUBLIC.fullmatch(source)
    if not match:
        raise ValueError("Use a local directory or a public https://github.com/OWNER/REPO URL.")
    owner, repo = match.groups()
    repo = repo.removesuffix(".git")
    if not repo or repo in {".", ".."}:
        raise ValueError("Invalid GitHub repository name.")
    return f"https://github.com/{owner.lower()}/{repo.lower()}"


def git(root, *args, stdin=None, discard=False):
    env = {"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
           "GIT_ALLOW_PROTOCOL": "", "GIT_NO_LAZY_FETCH": "1"}
    try:
        result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
                                input=stdin, stdout=subprocess.DEVNULL if discard else subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=env, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PolicyError("Local Git discovery requires a working git executable.") from exc
    return result


def ignored_by_git(root, names):
    if not names:
        return set()
    paths = b"\0".join(os.fsencode("./" + path) for path in names) + b"\0"
    result = git(root, "check-ignore", "--stdin", "-z", stdin=paths)
    if result.returncode not in (0, 1):
        raise PolicyError("Git ignore discovery failed. Check worktree access.")
    return {os.fsdecode(item).removeprefix("./") for item in result.stdout.split(b"\0") if item}


def local_capture(root: Path, locations: Locations):
    if not hasattr(os, "fwalk"):
        raise PolicyError("Local capture requires POSIX descriptor-relative file access.")
    if not root.is_dir():
        raise ValueError("Local source must be an existing directory.")
    managed = {p.resolve() for p in (locations.data, locations.cache, locations.config)}
    if any(root.is_relative_to(p) for p in managed):
        raise ValueError("Select a source outside CodeLens storage.")
    git_root = next((p for p in (root, *root.parents) if (p / ".git").is_file() or (p / ".git/HEAD").is_file()), None)
    commit = ""
    if git_root:
        result = git(root, "rev-parse", "--verify", "--quiet", "HEAD")
        if result.returncode not in (0, 1):
            raise PolicyError("Cannot read Git metadata.")
        commit = result.stdout.decode().strip()

    files = []
    total = entries = 0
    deadline = time.monotonic() + 120

    def fail(error):
        raise error

    for directory, dirs, names, parent in os.fwalk(root, onerror=fail, follow_symlinks=False):
        base = Path(directory)
        prefix = base.relative_to(root)
        entries += len(dirs) + len(names)
        if entries > MAX_ENTRIES or time.monotonic() > deadline:
            raise PolicyError("Repository discovery exceeded its entry or time limit.")
        dirs[:] = [d for d in dirs if not excluded(d) and base / d not in managed
                   and not (base / d).is_symlink() and not (base / d / ".git").exists()]
        names = [n for n in names if not excluded(n)]
        if git_root:
            ignored = ignored_by_git(root, [str(prefix / n) for n in dirs + names])
            # An ignored directory can still contain tracked files.
            for d in dirs.copy():
                relative = str(prefix / d)
                if relative in ignored:
                    tracked = git(root, "--literal-pathspecs", "ls-files", "--error-unmatch",
                                  "--", relative, discard=True)
                    if tracked.returncode == 1:
                        dirs.remove(d)
                    elif tracked.returncode:
                        raise PolicyError("Git tracked-file discovery failed.")
            names = [n for n in names if str(prefix / n) not in ignored]
        for name in names:
            path = (prefix / name).as_posix()
            path.encode("utf-8")  # SQLite TEXT requires a representable filename.
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                continue
            if len(files) >= MAX_FILES:
                raise PolicyError("Repository exceeds the file count limit.")
            if info.st_size > MAX_FILE:
                files.append(File(path, info.st_size, "oversize", None, None))
                continue
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, "rb") as stream:
                current = os.fstat(fd)
                if not stat.S_ISREG(current.st_mode) or not os.path.samestat(current, info):
                    raise PolicyError("Source changed during capture. Retry.")
                data = stream.read(MAX_FILE + 1)
                if len(data) != info.st_size or os.fstat(fd).st_mtime_ns != info.st_mtime_ns:
                    raise PolicyError("Source changed during capture. Retry.")
            total += len(data)
            if total > MAX_BYTES:
                raise PolicyError("Repository exceeds the byte limit.")
            files.append(File.capture(path, data))
    return Capture(str(root), "local", commit, files)


class GithubRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.netloc not in {"api.github.com", "codeload.github.com"}:
            raise PolicyError("GitHub returned an unexpected redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, accept, limit):
    request = Request(url, headers={"Accept": accept, "User-Agent": "CodeLens-local"})
    try:
        with build_opener(GithubRedirect()).open(request, timeout=15) as response:
            data = bytearray()
            deadline = time.monotonic() + 60
            while block := response.read1(65536):
                data.extend(block)
                if len(data) > limit or time.monotonic() > deadline:
                    raise PolicyError("GitHub download exceeded its size or time limit.")
            return bytes(data)
    except (URLError, TimeoutError, OSError) as exc:
        raise PolicyError("GitHub request failed. Check connectivity, public access, ref and rate limit.") from exc


def remote_capture(source, ref):
    ref = "HEAD" if ref is None else ref
    if not re.fullmatch(r"[\w./-]{1,255}", ref) or ".." in ref or ref.startswith(("/", "-")):
        raise ValueError("Invalid GitHub ref.")
    api = source.replace("https://github.com/", "https://api.github.com/repos/", 1)
    sha = download(f"{api}/commits/{quote(ref, safe='')}", "application/vnd.github.sha", 128).strip()
    if not re.fullmatch(b"[0-9a-f]{40}", sha):
        raise PolicyError("GitHub returned an invalid commit identity.")
    commit = sha.decode()
    packed = download(f"{api}/tarball/{commit}", "application/vnd.github+json", MAX_BYTES)
    files = []
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise PolicyError("Expanded archive exceeds the byte limit.")
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            for index, member in enumerate(archive):
                if index >= MAX_ENTRIES:
                    raise PolicyError("Archive exceeds the entry limit.")
                parts = PurePosixPath(member.name).parts
                if ".." in parts or member.name.startswith("/"):
                    raise PolicyError("Invalid archive path.")
                if len(parts) < 2 or not member.isfile() or any(map(excluded, parts[1:])):
                    continue
                path = "/".join(parts[1:])
                if len(files) >= MAX_FILES:
                    raise PolicyError("Archive exceeds the file count limit.")
                if member.size > MAX_FILE:
                    files.append(File(path, member.size, "oversize", None, None))
                else:
                    with archive.extractfile(member) as content:
                        files.append(File.capture(path, content.read()))
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise PolicyError("Unreadable GitHub archive.") from exc
    return Capture(source, "github", commit, files)
