"""Loaded as sitecustomize only in test children. Replace HTTP responses at the opener."""
import io
import json
import os
from pathlib import Path
import signal
import sys
import urllib.request
from urllib.error import HTTPError


def deny(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise AssertionError("Unexpected network access")


sys.addaudithook(deny)


class NoProvider:
    def find_spec(self, fullname, path, target=None):
        if fullname in {"codelens.providers", "codelens.settings"}:
            raise AssertionError("Saved read initialized generation")
        return None


if os.environ.get("READ_ONLY"):
    sys.meta_path.insert(0, NoProvider())


class Response(io.BytesIO):
    def readline(self, size=-1):
        if self.tell():
            mode = os.environ.get("STOP_STREAM")
            if mode == "interrupt":
                signal.raise_signal(signal.SIGINT)
            if mode == "kill":
                os._exit(77)
        return super().readline(size)


class Transport:
    def open(self, request, timeout):
        assert not os.environ.get("READ_ONLY")
        body = json.loads(request.data)
        with Path(os.environ["CALLS"]).open("a") as log:
            log.write(json.dumps(body) + "\n")
        system = body["messages"][0]["content"]
        mode = os.environ.get("FAIL", "")
        if mode == "api" and "Document evidenced routes" in system:
            raise HTTPError(request.full_url, 429, "rate limited", {}, None)
        first = "flowchart TD\nA-->B\n%% " if "raw Mermaid" in system else "Observation "
        last = "[E999]" if mode == "citation" else "[E1]"
        if request.full_url.endswith("/api/chat"):
            assert "Authorization" not in request.headers and body["options"]["num_predict"] > 0
            packets = [{"message": {"content": first}, "done": False},
                       {"message": {"content": last}, "done": True, "done_reason": "stop", "eval_count": 3}]
            lines = [json.dumps(p) for p in packets]
        else:
            assert request.full_url == "https://api.openai.com/v1/chat/completions"
            assert request.headers["Authorization"] == "Bearer fixture"
            assert body["stream_options"]["include_usage"] and body["max_completion_tokens"] > 0
            packets = [{"choices": [{"delta": {"content": first}, "finish_reason": None}]},
                       {"choices": [{"delta": {"content": last}, "finish_reason": "stop"}]},
                       {"choices": [], "usage": {"completion_tokens": 3}}]
            lines = ["data: " + json.dumps(p) for p in packets] + ["data: [DONE]"]
        if mode == "truncated":
            lines = lines[:1]
        return Response(("\n".join(lines) + "\n").encode())


urllib.request.build_opener = lambda *handlers: Transport()
