"""Fixed-argument process execution and redacted local operation results."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from . import settings


class OperationError(Exception):
    pass


def executable(name):
    variable = "ASTRA_" + name.upper().replace("-", "_")
    candidate = os.environ.get(variable) or shutil.which(name)
    local = settings.home() / "tools/node_modules/.bin" / name
    if local.is_file():
        return str(local)
    if candidate:
        return candidate
    for folder in (Path.home() / ".local/bin", Path.home() / ".npm-global/bin", Path.home() / ".npm-global/local/bin"):
        if (folder / name).is_file():
            return str(folder / name)
    raise OperationError(f"{name} is not installed. Open the installation guide in Help.")


def redact(text):
    text = str(text)
    try:
        key = settings.load().get("provider_api_key")
        if key:
            text = text.replace(key, "[private key]")
    except (OSError, ValueError):
        pass
    text = re.sub(r"(?i)(Bearer\s+)[^\s\"']+", r"\1[private]", text)
    text = re.sub(r"(?i)((?:access_token|refresh_token|client_secret|api_key|password|code|state)=)[^&\s]+", r"\1[private]", text)
    text = re.sub(r'(?i)(["\']?(?:access_token|refresh_token|client_secret|api_key|password|token)["\']?\s*[:=]\s*)["\']?[^\s,"\'}]+', r'\1[private]', text)
    return text[:12000]


class Runner:
    def run(self, name, arguments=(), *, timeout=30, data=None, env=None):
        argv = [executable(name), *(["--profile", settings.PROFILE] if name == "openclaw" else []), *map(str, arguments)]
        if name == "openclaw":
            env = dict(os.environ if env is None else env)
            for key in list(env):
                if key.startswith("OPENCLAW_"):
                    env.pop(key, None)
        if name == "npm":
            env = dict(os.environ if env is None else env)
            for key in ("NPM_CONFIG_PREFIX", "npm_config_prefix", "NPM_CONFIG_USERCONFIG", "npm_config_userconfig"):
                env.pop(key, None)
        env = dict(os.environ if env is None else env)
        env["PATH"] = str(settings.home() / "tools/node_modules/.bin") + os.pathsep + env.get("PATH", "")
        try:
            result = subprocess.run(argv, capture_output=True, text=True, input=data,
                                    timeout=timeout, env=env, cwd=settings.home() if settings.home().exists() else Path.home())
        except OSError as exc:
            raise OperationError(f"Cannot start {name}: {type(exc).__name__}") from exc
        except subprocess.TimeoutExpired as exc:
            raise OperationError("The operation timed out. Its outcome is uncertain; inspect current status before repeating it.") from exc
        if result.returncode:
            raise OperationError(redact(result.stderr or result.stdout or f"{name} exited with {result.returncode}"))
        return result.stdout

    def json(self, name, arguments=(), **kwargs):
        try:
            value = json.loads(self.run(name, arguments, **kwargs))
            if isinstance(value, dict) and value.get("ok") is False:
                raise OperationError("The tool reported an unsuccessful operation. Inspect its current status before retrying.")
            return value
        except json.JSONDecodeError as exc:
            raise OperationError("The tool returned an unexpected response. Check the installed tool version.") from exc


def require_idle(runner):
    response = runner.json("openclaw", ["gateway", "call", "sessions.list", "--params", '{"limit":1000}', "--json"])
    sessions = response.get("sessions")
    if not isinstance(sessions, list) or response.get("hasMore") or len(sessions) >= 1000:
        raise OperationError("Cannot establish that every session is idle. Open the runtime dashboard and check tasks.")
    if any(s.get("hasActiveRun") or s.get("hasActiveSubagentRun") or s.get("activeRunIds") or s.get("status") in ("running", "queued") for s in sessions):
        raise OperationError("A task is still running. Finish it before applying runtime changes or restarting.")
    return len(sessions)
