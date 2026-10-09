"""User-supplied Desktop OAuth client and isolated, private gog keyring."""
import json
import os
from pathlib import Path
import secrets
from . import settings
from .commands import OperationError, Runner

SERVICES = "gmail,calendar,drive,docs,sheets,slides,contacts,tasks,forms"


def environment():
    root = settings.home() / "private/google"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    path = root / "keyring-password"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GOG_",))}
    env.update(GOG_HOME=str(root), GOG_ACCOUNT=settings.load()["google_email"],
               GOG_KEYRING_BACKEND="file", GOG_KEYRING_PASSWORD=path.read_text())
    return env


def gog(arguments, runner=None, timeout=30):
    email = settings.load()["google_email"]
    if not email:
        raise OperationError("Enter your Google account email in Connections")
    return (runner or Runner()).run("gog", ["--client", "astra", "--account", email, *arguments],
                                    env=environment(), timeout=timeout)


def status(runner=None):
    response = json.loads(gog(["auth", "list", "--json", "--no-input"], runner))
    account = next((a for a in response.get("accounts", []) if a.get("email") == settings.load()["google_email"]), None)
    return {"authorized": bool(account), "services": account.get("services", []) if account else []}


def import_client(client):
    installed = client.get("installed", {}) if isinstance(client, dict) else {}
    if not installed.get("client_id") or not installed.get("client_secret"):
        raise OperationError("Choose the Desktop app OAuth JSON downloaded from your own Google Cloud project")
    path = settings.home() / "private/google/desktop-client.json"
    settings.write_private(path, client)
    value = settings.load()
    value["google_client_file"] = str(path)
    settings.write_private(settings.settings_path(), value)
    return {"message": "Desktop client saved privately on this computer. You can now connect Google."}


def login(runner=None):
    cfg = settings.load()
    if not cfg["google_email"] or not cfg["google_client_file"]:
        raise OperationError("Enter your email and choose your Desktop OAuth JSON first")
    path = Path(cfg["google_client_file"]).expanduser()
    client = json.loads(path.read_text())
    if not client.get("installed", {}).get("client_secret"):
        raise OperationError("The selected file is not a Desktop OAuth client")
    gog(["auth", "credentials", "set", str(path)], runner)
    gog(["auth", "add", cfg["google_email"], "--services", SERVICES, "--listen-addr", "127.0.0.1",
         "--timeout", "15m", "--force-consent"], runner, timeout=930)
    gog(["auth", "list", "--check", "--no-input"], runner)
    return status(runner)
