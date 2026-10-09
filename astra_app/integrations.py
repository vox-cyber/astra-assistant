"""Local integration operations with explicit user initiation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import socket
import sys
import tarfile
import time
from . import settings, runtime
from .commands import OperationError, Runner, executable, require_idle


def inspect():
    tools = {}
    for name in ("node", "openclaw", "omniroute", "gog", "wacli", "adb", "scrcpy", "tailscale", "syncthing", "pactl", "ffplay"):
        try:
            runtime.local_executable(name) if name in ("openclaw", "omniroute") else executable(name)
            tools[name] = True
        except OperationError:
            tools[name] = False
    return {"python": sys.version.split()[0], "platform": sys.platform, "tools": tools,
            "private_core": {name: tools[name] for name in ("openclaw", "omniroute")},
            "profile": settings.PROFILE, "settings": settings.public(), "private_directory": str(settings.home())}


def health(runner=None):
    if not settings.load()["runtime_configured"]:
        return {"ready": False, "message": "Runtime not configured"}
    runner = runner or Runner()
    try:
        result = runtime.call("astra.replyGuard.status", runner=runner)
        ready = result.get("ownerConfigured") is True and result.get("messagingGuard", {}).get("storageAvailable") is True
        return {"ready": ready, "gateway_available": True, "guard": result,
                "message": "Guard responded. Model, account and delivery checks are separate."}
    except OperationError as exc:
        return {"ready": False, "message": str(exc)}


def whatsapp_link(runner=None):
    if not settings.load()["runtime_configured"]:
        raise OperationError("Apply runtime setup and start the gateway first")
    return runtime.call("web.login.start", {"force": False, "accountId": "default"}, runner)


def whatsapp_wait(runner=None):
    return runtime.call("web.login.wait", {"accountId": "default", "timeoutMs": 20000}, runner)


def instagram_login(runner=None):
    runner = runner or Runner()
    require_idle(runner)
    profiles = runner.json("openclaw", ["browser", "profiles", "--json"]).get("profiles", [])
    if not any(p.get("name") == "instagram" for p in profiles):
        runner.run("openclaw", ["browser", "create-profile", "--name", "instagram", "--color", "#ae8bfa"])
    runner.run("openclaw", ["browser", "--browser-profile", "instagram", "stop"])
    runner.run("openclaw", ["browser", "--browser-profile", "instagram", "start"], timeout=40)
    runner.run("openclaw", ["browser", "--browser-profile", "instagram", "open", "https://www.instagram.com/direct/inbox/"])
    return {"message": "Sign into your own account in the browser window. Complete any genuine account challenges there."}


def phone_status(runner=None):
    output = (runner or Runner()).run("adb", ["devices", "-l"])
    return {"text": output}


def phone_screen(serial):
    if not isinstance(serial, str) or not serial or len(serial) > 200 or serial.startswith("-"):
        raise OperationError("Choose the intended device serial from phone status")
    subprocess.Popen([executable("scrcpy"), "--serial", serial], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"message": "scrcpy launched for the selected device. Verify its window and device permission prompts."}


def history(arguments, runner=None):
    if not arguments or arguments[0] not in ("messages", "chats", "contacts", "doctor") or "send" in arguments:
        raise OperationError("Use history for read-only messages, chats, contacts or doctor commands")
    return {"text": (runner or Runner()).run("wacli", ["--store", str(settings.home() / "private/wacli"), "--read-only", *arguments])}


def unit_quote(value):
    value = str(value)
    if any(c in value for c in "\n\r\x00"):
        raise OperationError("Invalid service path")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def install_services(runner=None):
    if sys.platform != "linux":
        raise OperationError("Persistent services currently require a Linux host")
    runner = runner or Runner()
    folder = Path.home() / ".config/systemd/user"
    folder.mkdir(parents=True, exist_ok=True)
    python = unit_quote(sys.executable)
    cwd = unit_quote(settings.PROJECT)
    astra_home = unit_quote("ASTRA_HOME=" + str(settings.home()))
    helper = settings.resources() / "plugins" / runtime.PLUGIN / "voice-player.py"
    templates = {
        "astra-community-dashboard.service": f"ExecStart={python} -m astra_app serve --no-browser\n",
        "astra-community-voice.service": f"ExecStart={python} {unit_quote(helper)} worker --state-dir {unit_quote(settings.home() / 'private/runtime/voice')} --inbound-dir {unit_quote(runtime.profile_home() / 'media/inbound')}\n",
        "astra-community-recovery.service": f"ExecStart={python} -m astra_app worker recovery\n",
        "astra-community-history.service": f"ExecStart={python} -m astra_app worker history\n",
    }
    for name, command in templates.items():
        path = folder / name
        restart = "no" if name.endswith("history.service") else "on-failure"
        content = f"[Unit]\nDescription=Astra community {name}\nAfter=default.target\n\n[Service]\nType=simple\nWorkingDirectory={cwd}\nEnvironment={astra_home}\n{command}Restart={restart}\nRestartSec=5\nUMask=0077\n\n[Install]\nWantedBy=default.target\n"
        if path.exists() and path.read_text() != content:
            raise OperationError(f"Existing {name} differs. Preserve it and inspect it before replacing it.")
        path.write_text(content)
        path.chmod(0o600)
    runner.run("systemctl", ["--user", "daemon-reload"])
    return {"message": "Dashboard, voice, guarded recovery and history user units installed. Enable/start only those you want using the Services guide."}


def backup(runner=None):
    try:
        connection = socket.create_connection(("127.0.0.1", 18791), timeout=1)
    except OSError:
        connection = None
    if connection:
        connection.close()
        raise OperationError("Stop the Astra gateway, browser, history sync and recovery services before taking a consistent private backup")
    root = settings.home().resolve()
    target = Path.home() / ".local/share/astra-backups"
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.chmod(0o700)
    path = target / ("astra-private-" + str(time.time_ns()) + ".tar.gz")
    if path.resolve().is_relative_to(root):
        raise OperationError("The backup destination must be outside ASTRA_HOME")
    with tarfile.open(path, "w:gz") as archive:
        for name, location in (("astra", root), ("openclaw-profile", runtime.profile_home())):
            if location.exists():
                def filtered(info):
                    # Avoid browser sockets/cache and all symlinks/devices.
                    if not (info.isfile() or info.isdir()) or any(p in ("Cache", "Code Cache", "GPUCache", "SingletonLock", "SingletonSocket") for p in Path(info.name).parts):
                        return None
                    return info
                archive.add(location, arcname=name, filter=filtered)
    path.chmod(0o600)
    return {"message": "Private backup created. It contains account data: keep it encrypted/offline and never upload it to GitHub.", "path": str(path)}
