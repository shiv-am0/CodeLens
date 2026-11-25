"""Synchronous streaming adapters. Closing the iterator releases its HTTP connection."""
from dataclasses import dataclass
from http.client import HTTPException
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .domain import GenerationError, PolicyError


@dataclass
class Event:
    text: str = ""
    usage: dict | None = None
    done: bool = False

    def __post_init__(self):
        if not isinstance(self.text, str) or (self.usage is not None and not isinstance(self.usage, dict)):
            raise GenerationError("Malformed provider text or usage event.")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def frames(url, body, headers, local):
    request = Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    handlers = [NoRedirect()]
    if local:
        handlers.append(ProxyHandler({}))
    try:
        with build_opener(*handlers).open(request, timeout=60) as response:
            deadline = time.monotonic() + 600
            total = 0
            while line := response.readline(1024 * 1024 + 1):
                total += len(line)
                if len(line) > 1024 * 1024 or total > 16 * 1024 * 1024 or time.monotonic() > deadline:
                    raise GenerationError("Provider stream exceeded its time or byte budget.")
                yield line.decode("utf-8").strip()
    except HTTPError as exc:
        advice = {401: "Check your API credential.", 403: "Check model access.",
                  404: "Check the configured model and endpoint.", 429: "Retry after the provider rate limit."}
        raise GenerationError(f"Provider HTTP {exc.code}. " + advice.get(exc.code, "Check model options or provider status.")) from None
    except (URLError, OSError, UnicodeError, HTTPException) as exc:
        raise GenerationError("Provider connection failed or the stream was interrupted.") from exc


def openai(settings, messages):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise PolicyError("OpenAI generation requires OPENAI_API_KEY in the environment.")
    body = dict(model=settings.model, messages=messages, stream=True,
                max_completion_tokens=settings.output_tokens, stream_options={"include_usage": True})
    stopped = False
    for line in frames(settings.endpoint + "/v1/chat/completions", body, {"Authorization": "Bearer " + key}, False):
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            if stopped:
                yield Event(done=True)
                return
            break
        packet = json.loads(data)
        if "error" in packet:
            raise GenerationError("OpenAI reported a streaming error.")
        for choice in packet["choices"]:
            reason = choice.get("finish_reason")
            if reason and reason != "stop":
                raise GenerationError("OpenAI did not finish a complete text response. Check the output budget.")
            stopped |= reason == "stop"
            if text := choice["delta"].get("content"):
                yield Event(text=text)
        if packet.get("usage"):
            yield Event(usage=packet["usage"])
    raise GenerationError("Incomplete OpenAI stream.")


def ollama(settings, messages):
    body = dict(model=settings.model, messages=messages, stream=True, options={"num_predict": settings.output_tokens})
    for line in frames(settings.endpoint + "/api/chat", body, {}, True):
        if not line:
            continue
        packet = json.loads(line)
        if "error" in packet:
            raise GenerationError("Ollama reported an error. Check the runtime and installed model.")
        if text := packet.get("message", {}).get("content"):
            yield Event(text=text)
        if packet.get("done"):
            if packet.get("done_reason") not in (None, "stop"):
                raise GenerationError("Ollama stopped before completing the response. Check the output budget.")
            usage = {k: packet[k] for k in ("prompt_eval_count", "eval_count") if k in packet}
            yield Event(usage=usage or None, done=True)
            return
    raise GenerationError("Incomplete Ollama stream.")


def stream(settings, messages):
    adapter = {"openai": openai, "ollama": ollama}[settings.provider]
    try:
        yield from adapter(settings, messages)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise GenerationError("Malformed provider stream.") from exc
