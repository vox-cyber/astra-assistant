"""Authenticated loopback dashboard with a fixed operation allowlist."""
from collections import OrderedDict
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit, parse_qs
import webbrowser
from . import settings, integrations, runtime, tasks, google, persona, notes
from .commands import OperationError, Runner, redact

WEB = Path(__file__).with_name("web")
HELP = {"INSTALL.md", "USAGE.md", "INTEGRATIONS.md", "FEATURES.md", "PRIVACY.md", "TROUBLESHOOTING.md", "DEVELOPMENT.md"}


def token():
    path = settings.home() / "private/dashboard-token.json"
    if not path.exists():
        settings.write_private(path, {"token": secrets.token_urlsafe(36)})
    return json.loads(path.read_text())["token"]


def dispatch(action, params):
    if action == "settings.save":
        return settings.save(params)
    if action == "runtime.apply":
        return runtime.apply()
    if action == "bootstrap":
        return runtime.bootstrap()
    if action.startswith("router."):
        return runtime.router(action.removeprefix("router."))
    if action == "away.window":
        return runtime.away_window(params.get("hours", 5))
    if action.startswith("gateway."):
        return runtime.gateway(action.removeprefix("gateway."))
    if action == "health":
        return integrations.health()
    if action == "model.catalog":
        return runtime.model_check()
    if action == "model.test":
        return runtime.model_check(True)
    if action == "ask":
        return runtime.ask(params.get("prompt"))
    if action == "whatsapp.link":
        return integrations.whatsapp_link()
    if action == "whatsapp.wait":
        return integrations.whatsapp_wait()
    if action == "google.import":
        return google.import_client(params.get("client"))
    if action == "google.login":
        return google.login()
    if action == "google.status":
        return google.status()
    if action == "google.check":
        response = json.loads(google.gog(["drive", "ls", "--max", "1", "--json", "--no-input"]))
        return {"message": "Google Drive read API responded. Other services require their own checks.", "drive_read_verified": isinstance(response, (dict, list))}
    if action == "instagram.login":
        return integrations.instagram_login()
    if action in ("instagram.create", "instagram.enable", "instagram.disable"):
        return runtime.instagram_watch(action == "instagram.enable", create=action == "instagram.create")
    if action == "phone.status":
        return integrations.phone_status()
    if action == "phone.screen":
        return integrations.phone_screen(params.get("serial"))
    if action == "persona.collect":
        return persona.collect(params.get("before"))
    if action == "persona.status":
        return persona.status()
    if action == "notes.init":
        return notes.initialize()
    if action == "calendar.export":
        return notes.event(params["title"], params["start"], params["end"])
    if action == "tasks.create":
        return tasks.create(params.get("title"), at=params.get("at"), every=params.get("every"),
                            expression=params.get("expression"), assignee=params.get("assignee", "me"))
    if action in ("tasks.complete", "tasks.cancel"):
        return tasks.finish(params.get("id"), "completed" if action == "tasks.complete" else "cancelled")
    if action == "tasks.postpone":
        return tasks.postpone(params.get("id"), params.get("at"))
    if action == "tasks.reconcile":
        return tasks.reconcile(params.get("id"))
    if action in ("guard.pause", "guard.resume"):
        return runtime.call("astra.messagingGuard." + action.split(".")[1], {"platform": params.get("platform"), "reviewed": params.get("reviewed") is True})
    if action == "services.install":
        return integrations.install_services()
    if action == "backup":
        return integrations.backup()
    raise OperationError("Unknown operation")


class Jobs:
    def __init__(self, handler=dispatch):
        self.handler, self.lock, self.jobs, self.busy = handler, threading.Lock(), OrderedDict(), False

    def submit(self, action, params):
        with self.lock:
            if self.busy:
                raise OperationError("An operation is already running. Finish it before starting another.")
            self.busy = True
            identifier = secrets.token_hex(12)
            self.jobs[identifier] = {"id": identifier, "action": action, "state": "running"}
            while len(self.jobs) > 100:
                self.jobs.popitem(last=False)
        threading.Thread(target=self.run, args=(identifier, action, params), daemon=True).start()
        return identifier

    def run(self, identifier, action, params):
        try:
            result = self.handler(action, params)
            value = {"state": "completed", "result": result}
        except Exception as exc:
            # Native errors are redacted; unexpected errors do not expose traces or input.
            text = redact(str(exc)) if isinstance(exc, (OperationError, ValueError)) else f"Operation failed ({type(exc).__name__}). See Troubleshooting."
            value = {"state": "failed", "error": text}
        with self.lock:
            self.jobs[identifier].update(value)
            self.busy = False

    def get(self, identifier):
        with self.lock:
            return dict(self.jobs[identifier]) if identifier in self.jobs else None


class Dashboard(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, secret, jobs=None):
        if address[0] != "127.0.0.1":
            raise ValueError("The dashboard binds only to IPv4 loopback")
        self.secret, self.jobs = secret, jobs or Jobs()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "AstraLocal/0.1"

    def log_message(self, *_):
        pass  # Do not log auth URLs, account input or private operation results.

    def allowed(self, authenticated=False):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts:
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {"http://" + h for h in hosts}:
            return False
        if authenticated:
            expected = "Bearer " + self.server.secret
            return hmac.compare_digest(self.headers.get("Authorization", ""), expected)
        return True

    def send(self, code, body, content_type="application/json; charset=utf-8"):
        encoded = json.dumps(body, ensure_ascii=False).encode() if content_type.startswith("application/json") else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        url = urlsplit(self.path)
        api = url.path.startswith("/api/")
        if not self.allowed(api):
            return self.send(403, {"error": "Open the private dashboard link printed by Astra."})
        try:
            if url.path == "/api/status":
                return self.send(200, integrations.inspect())
            if url.path == "/api/tasks":
                return self.send(200, tasks.list_tasks("all"))
            if url.path.startswith("/api/jobs/"):
                job = self.server.jobs.get(url.path.split("/")[-1])
                return self.send(200 if job else 404, job or {"error": "Operation not found"})
            if url.path == "/api/help":
                name = parse_qs(url.query).get("name", ["INSTALL.md"])[0]
                if name not in HELP:
                    return self.send(404, {"error": "Guide not found"})
                path = settings.resources() / "docs" / name
                return self.send(200, {"name": name, "text": path.read_text(encoding="utf-8")})
            if api:
                return self.send(404, {"error": "Route not found"})
            assets = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
            if url.path not in assets:
                return self.send(404, {"error": "Page not found"})
            path = WEB / assets[url.path]
            return self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] + "; charset=utf-8")
        except (ValueError, OSError, OperationError) as exc:
            return self.send(500, {"error": redact(str(exc))})

    def do_POST(self):
        if not self.allowed(True):
            return self.send(403, {"error": "Private local authentication required"})
        if self.path != "/api/actions":
            return self.send(404, {"error": "Route not found"})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.send(415, {"error": "Send a JSON request"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2 * 1024 * 1024:
                return self.send(413, {"error": "Request size is invalid"})
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict) or not isinstance(value.get("action"), str) or not isinstance(value.get("params", {}), dict):
                raise ValueError("Invalid operation request")
            identifier = self.server.jobs.submit(value["action"], value.get("params", {}))
            return self.send(202, {"id": identifier})
        except (ValueError, OperationError) as exc:
            return self.send(400, {"error": redact(str(exc))})


def serve(port=8765, open_browser=True):
    if not 1024 <= port <= 65535:
        raise ValueError("Choose a port between 1024 and 65535")
    secret = token()
    server = Dashboard(("127.0.0.1", port), secret)
    link = f"http://127.0.0.1:{port}/#session={secret}"
    print("Astra local setup: " + link, flush=True)
    print("This link controls your local assistant. Keep it private. Ctrl+C stops the dashboard.", flush=True)
    if open_browser:
        webbrowser.open(link)
    try:
        server.serve_forever()
    finally:
        server.server_close()
