"""Run explicitly with the installed CLI interpreter. Requires loopback socket access."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread

sent = Event()
release = Event()

class Runtime(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        assert self.path == "/api/chat"
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        assert body["model"] == "fixture" and "print(42)" in body["messages"][-1]["content"]
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        self.wfile.write(b'{"message":{"content":"Observed "},"done":false}\n')
        self.wfile.flush()
        sent.set()
        assert release.wait(10)
        self.wfile.write(b'{"message":{"content":"[E1]"},"done":true,"done_reason":"stop"}\n')

def main():
    with TemporaryDirectory() as temp, HTTPServer(("127.0.0.1", 0), Runtime) as server:
        worker = Thread(target=server.handle_request, daemon=True)
        worker.start()
        root = Path(temp)
        source = root / "src"
        source.mkdir()
        (source / "main.py").write_text("print(42)\n")
        env = {"PATH": os.defpath, "CODELENS_HOME": str(root / "home")}
        cli = str(Path(sys.executable).with_name("codelens"))
        def run(*args):
            return json.loads(subprocess.check_output([cli, *args, "--json"], cwd=temp, env=env))
        sid = run("open", str(source))["session_id"]
        run("setup", "--provider", "ollama", "--model", "fixture", "--endpoint", "http://127.0.0.1:" + str(server.server_port))
        with subprocess.Popen([cli, "ask", sid, "What runs?"], stdout=subprocess.PIPE, env=env, cwd=temp) as proc:
            assert sent.wait(5)
            assert proc.stdout.read(9) == b"Observed "
            assert run("history", sid, "--offline")[-1]["status"] == "running"
            release.set()
            assert proc.wait(10) == 0
        worker.join(5)
        assert run("history", sid, "--offline")[-1]["status"] == "complete"
    print("Real loopback HTTP adapter: first delta before completion, concurrent offline read, final commit passed.")


if __name__ == "__main__":
    main()
