"""Optional model-free background recovery and pause-aware local history sync."""
import subprocess
import time
import re
from . import settings, runtime
from .commands import OperationError, Runner, executable, require_idle


def permitted(runner):
    value = runtime.call("astra.messagingGuard.status", runner=runner)
    return value.get("storageAvailable") is True and isinstance(value.get("paused"), dict) and not value["paused"].get("whatsapp")


def recover_once(runner=None):
    runner = runner or Runner()
    if not permitted(runner):
        return "paused"
    data = runtime.call("channels.status", {"probe": False}, runner)
    accounts = data.get("channelAccounts", {}).get("whatsapp", [])
    channel = next((a for a in accounts if a.get("accountId") == "default"), data.get("channels", {}).get("whatsapp", {}))
    if channel.get("connected") is True:
        return "connected"
    if channel.get("linked") is not True or channel.get("enabled") is False:
        return "needs_link"
    error = str(channel.get("lastError") or channel.get("lastDisconnect") or "")
    code = "PLATFORM_RATE_LIMIT" if re.search(r"429|rate.?limit|too many requests", error, re.I) else \
        "PLATFORM_VERIFICATION" if re.search(r"challenge|checkpoint|verification|captcha|logged.?out|login_required", error, re.I) else \
        "PLATFORM_RESTRICTED" if re.search(r"banned|suspended|restricted|action blocked", error, re.I) else None
    if code:
        runtime.call("astra.messagingGuard.reportRestriction", {"platform": "whatsapp", "code": code}, runner)
        return "restricted"
    if not re.search(r"ECONNRESET|ETIMEDOUT|EPIPE|connection (?:closed|lost)|keepalive|network|timed out", error, re.I):
        return "unclassified_disconnect"
    path = settings.home() / "private/recovery.json"
    import json
    history = json.loads(path.read_text()).get("restarts", []) if path.exists() else []
    current = time.time()
    history = [at for at in history if current - at < 86400]
    if len(history) >= 6 or any(current - at < 900 for at in history):
        return "restart_ceiling"
    # Only a proved authenticated, unpaused transient disconnection may restart.
    require_idle(runner)
    settings.write_private(path, {"restarts": [*history, current]})
    runtime.gateway("restart", runner)
    return "restart_requested"


def recovery():
    while True:
        try:
            recover_once()
        except (OperationError, ValueError):
            pass  # Unknown/unavailable/active state never authorizes a restart.
        time.sleep(120)


def history():
    runner = Runner()
    if not permitted(runner):
        raise OperationError("History sync cannot start while account status is paused or unavailable")
    child = subprocess.Popen([executable("wacli"), "--store", str(settings.home() / "private/wacli"), "sync", "--follow",
                              "--presence-mode", "quiet", "--max-reconnect", "2m", "--max-db-size", "1GB"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        while child.poll() is None:
            time.sleep(10)
            if not permitted(runner):
                raise OperationError("History sync stopped because platform authorization is paused/unavailable")
        raise OperationError("History sync exited. Inspect authentication/account status before manually restarting it.")
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
