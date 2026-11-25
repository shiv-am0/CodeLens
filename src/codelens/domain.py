"""Capture policy and immutable values passed between discovery and storage."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import os

from platformdirs import user_cache_path, user_config_path, user_data_path

MAX_FILES = 3000
MAX_BYTES = 100 * 1024 * 1024
MAX_FILE = 512 * 1024
MAX_ENTRIES = 100_000
POLICY = json.dumps({"ignore": 1, "parser": "utf8-lf-v1", "chunker": "80-lines-8k-v1",
                     "file_limit": MAX_FILE, "version": 1}, sort_keys=True)


class PolicyError(Exception):
    """An unavailable capability or disallowed operation."""


class GenerationError(Exception):
    """A provider or response validation failure."""


class Missing(Exception):
    """A requested saved record does not exist."""


@dataclass(frozen=True)
class Locations:
    data: Path
    config: Path
    cache: Path

    @classmethod
    def configured(cls):
        override = os.environ.get("CODELENS_HOME")
        if override:
            root = Path(override).expanduser().resolve()
            return cls(root / "data", root / "config", root / "cache")
        return cls(*(fn("codelens") for fn in (user_data_path, user_config_path, user_cache_path)))


@dataclass(frozen=True)
class File:
    path: str
    size: int
    coverage: str
    data: bytes | None
    digest: str | None

    @classmethod
    def capture(cls, path: str, data: bytes):
        digest = hashlib.sha256(data).hexdigest()
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return cls(path, len(data), "non-utf8", None, digest)
        if b"\0" in data:
            return cls(path, len(data), "binary", None, digest)
        return cls(path, len(data), "full", data, digest)


@dataclass(frozen=True)
class Capture:
    source: str
    kind: str
    commit: str
    files: list[File]

    def manifest(self):
        rows = sorted((f.path, f.size, f.coverage, f.digest) for f in self.files)
        return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
