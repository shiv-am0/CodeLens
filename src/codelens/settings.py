"""User-scoped generation settings; secrets are resolved only at inference time."""
from dataclasses import asdict, dataclass
import json
import os
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from .domain import PolicyError


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    endpoint: str
    input_bytes: int
    output_tokens: int

    def __post_init__(self):
        if self.provider not in {"openai", "ollama"} or not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Select openai or ollama and provide an explicit model ID.")
        if not 2048 <= self.input_bytes <= 262144 or not 1 <= self.output_tokens <= 65536:
            raise ValueError("Input budget must be 2048–262144 bytes and output budget 1–65536 tokens.")
        url = urlsplit(self.endpoint)
        if self.provider == "openai":
            if self.endpoint != "https://api.openai.com":
                raise ValueError("OpenAI requires the official API endpoint.")
        elif (url.scheme not in {"http", "https"} or url.hostname not in {"localhost", "127.0.0.1", "::1"}
              or url.username or url.password or url.path or url.query or url.fragment):
            raise ValueError("Ollama requires a loopback base URL with no path or credentials.")
        _ = url.port


def configure(locations, provider, model, endpoint, input_bytes, output_tokens):
    default = "https://api.openai.com" if provider == "openai" else "http://127.0.0.1:11434"
    settings = Settings(provider, model, (endpoint or default).rstrip("/"), input_bytes, output_tokens)
    locations.config.mkdir(mode=0o700, parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=locations.config, delete=False) as tmp:
        json.dump(asdict(settings), tmp)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, locations.config / "generation.json")
    return asdict(settings)


def load(locations):
    try:
        return Settings(**json.loads((locations.config / "generation.json").read_text()))
    except FileNotFoundError as exc:
        raise PolicyError("Run codelens setup --provider NAME --model ID before generation.") from exc
    except (TypeError, ValueError, AttributeError) as exc:
        raise PolicyError("Invalid generation settings. Run codelens setup again.") from exc
