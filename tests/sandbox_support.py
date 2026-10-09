"""Disposable fixtures; no real native tools, accounts, or inherited credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT = Path(__file__).resolve().parents[1]


class Sandbox:
    def __init__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="astra fake sandbox ")
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.data = self.root / "astra"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        driver = self.bin / "fake-driver"
        driver.write_text(f"#!{sys.executable}\n" + (PROJECT / "tests/fake_tools.py").read_text())
        driver.chmod(0o700)
        for name in ("node", "npm", "gog", "wacli", "adb", "scrcpy", "systemctl"):
            (self.bin / name).symlink_to(driver)
        self.env = {"PATH": str(self.bin), "HOME": str(self.home), "USERPROFILE": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_CACHE_HOME": str(self.home / ".cache"), "ASTRA_HOME": str(self.data), "ASTRA_FAKE_ROOT": str(self.root),
            "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8", "TMPDIR": str(self.root)}
        self.http_calls = []
        self.model_reply = "READY"
        outer = self

        class Model(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                outer.http_calls.append(("GET", self.path))
                self.reply({"data": [{"id": "kg/kilo-auto/free"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.http_calls.append(("POST", self.path, body))
                self.reply({"choices": [{"message": {"content": outer.model_reply}}]})

            def reply(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.model = ThreadingHTTPServer(("127.0.0.1", 0), Model)
        self.thread = threading.Thread(target=self.model.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.model.server_port}/v1"

    def close(self):
        self.model.shutdown()
        self.model.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    def cli(self, *args, data=None, success=True, raw=False):
        result = subprocess.run([sys.executable, str(PROJECT / "launch.py"), *args], env=self.env,
            cwd=self.root, input=json.dumps(data) if data is not None else None, text=True, capture_output=True, timeout=30)
        if success and result.returncode:
            raise AssertionError(f"CLI failed {args}: {result.stderr}")
        if not success:
            if not result.returncode:
                raise AssertionError(f"CLI unexpectedly succeeded {args}: {result.stdout}")
            return result.stderr
        return result.stdout if raw else json.loads(result.stdout)

    def native(self):
        path = self.root / "native.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def control(self, **changes):
        state = self.native()
        state.update(changes)
        (self.root / "native.json").write_text(json.dumps(state))

    def setup(self):
        self.cli("configure", data={"owner_name": "Sandbox Owner", "owner_phone": "+15555550100",
            "google_email": "owner@example.invalid", "instagram_username": "synthetic_account",
            "provider_url": self.url, "provider_api_key": "sandbox-only-key", "away_enabled": True})
        self.cli("bootstrap")
        self.cli("apply")
        self.cli("gateway", "install")
        self.cli("gateway", "start")

    def assert_contained(self):
        for entry in self.native().get("calls", []):
            assert entry["tool"] in ("node", "npm", "openclaw", "omniroute", "gog", "wacli", "adb", "scrcpy", "systemctl")
            for name in ("HOME", "ASTRA_HOME", "GOG_HOME", "DATA_DIR"):
                if name in entry["env"]:
                    assert Path(entry["env"][name]).is_relative_to(self.root), entry
            if entry["tool"] == "openclaw":
                assert entry["args"][:2] == ["--profile", "astra-community"]
