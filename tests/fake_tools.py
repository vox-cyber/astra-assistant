"""Strict fake native tools. Executed as real subprocesses, never a real account client."""
import fcntl
import json
import os
from pathlib import Path
import sys
import time


def main():
    root = Path(os.environ["ASTRA_FAKE_ROOT"])
    tool, args = Path(sys.argv[0]).name, sys.argv[1:]
    state_path = root / "native.json"
    with (root / "native.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        state.setdefault("calls", []).append({"tool": tool, "args": args,
            "env": {k: os.environ[k] for k in ("HOME", "ASTRA_HOME", "GOG_HOME", "GOG_ACCOUNT", "DATA_DIR",
                "OMNIROUTE_SERVER_HOST", "LIVE_WS_PORT", "EMBED_WS_PROXY_PORT") if k in os.environ}})
        try:
            result = dispatch(tool, args, state, root)
            print(result if isinstance(result, str) else json.dumps(result))
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        finally:
            state_path.write_text(json.dumps(state))
        return 0


def dispatch(tool, args, state, root):
    def flag(name, default=None):
        return args[args.index(name) + 1] if name in args else default

    if tool == "node" and args == ["--version"]:
        return "v24.21.0"
    if tool == "npm" and args[:1] == ["install"]:
        assert "--prefix" in args and "-g" not in args
        if state.get("install_failure"):
            raise RuntimeError("Synthetic package download failed")
        target = Path(flag("--prefix")) / "node_modules/.bin"
        assert target.is_relative_to(root)
        target.mkdir(parents=True, exist_ok=True)
        for name in ("openclaw", "omniroute"):
            binary = target / name
            if not binary.exists():
                binary.symlink_to(root / "bin/fake-driver")
        return "Synthetic packages installed"
    if tool == "omniroute":
        if args == ["--version"]:
            return state.get("router_version", "3.8.51")
        if args[0] in ("serve", "restart", "stop"):
            assert Path(os.environ["DATA_DIR"]).is_relative_to(root)
            assert Path.home().is_relative_to(root)
            assert os.environ["OMNIROUTE_SERVER_HOST"] == "127.0.0.1"
            state["router_running"] = args[0] != "stop"
            return "Synthetic router command accepted"
    if tool == "systemctl":
        assert args == ["--user", "daemon-reload"]
        return ""
    if tool == "adb" and args == ["devices", "-l"]:
        return "List of devices attached\nSYNTHETIC-DEVICE device model:Sandbox\n"
    if tool == "scrcpy" and args == ["--serial", "SYNTHETIC-DEVICE"]:
        return ""
    if tool == "gog":
        assert flag("--client") == "astra"
        assert Path(os.environ["GOG_HOME"]).is_relative_to(root)
        assert "GOG_ACCESS_TOKEN" not in os.environ
        if "credentials" in args:
            return {"ok": True}
        if "add" in args:
            state["google_authorized"] = True
            return {"ok": True}
        if "auth" in args:
            return {"accounts": [{"email": flag("--account"), "services": ["drive", "gmail"]}] if state.get("google_authorized") else []}
        if "drive" in args:
            return {"files": []}
    if tool == "wacli":
        assert "--read-only" in args and Path(flag("--store")).is_relative_to(root)
        if "list" in args:
            rows = [{"FromMe": True, "ChatJID": "15555550102@s.whatsapp.net", "Text": f"Synthetic style message {i}",
                     "MsgID": f"synthetic-{i}", "Timestamp": "2020-01-01T00:00:00Z"} for i in range(8)]
            rows.append({"FromMe": True, "ChatJID": "15555550102@s.whatsapp.net", "Text": "password: omit this evidence"})
            return {"success": True, "data": {"messages": rows}}
        return {"success": True, "data": {"messages": []}}
    if tool != "openclaw":
        raise RuntimeError(f"Unimplemented fake tool: {tool}")
    assert args[:2] == ["--profile", "astra-community"], "Profile isolation missing"
    assert not any(k.startswith("OPENCLAW_") for k in os.environ), "Inherited native override leaked"
    args = args[2:]
    if args == ["--version"]:
        return state.get("core_version", "OpenClaw 2026.9.1 (synthetic)")
    if args[:2] == ["plugins", "install"]:
        return "Synthetic plugin installed"
    if args[:2] == ["config", "patch"]:
        value = json.load(sys.stdin)
        if "--dry-run" in args:
            return {"ok": not state.get("invalid_schema"), "checks": {"schema": not state.get("invalid_schema"), "resolvabilityComplete": True}}
        state["config"] = value
        profile = Path.home() / ".openclaw-astra-community"
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "openclaw.json").write_text(json.dumps(value))
        return "Synthetic config saved"
    if args[:1] == ["agent"]:
        if state.get("agent_failure"):
            return {"status": "error", "error": "Synthetic agent failed", "result": {"payloads": []}}
        return {"status": "ok", "result": {"payloads": [{"text": "Synthetic answer: <img src=x onerror=alert('unsafe')>"}]}}
    if args[:2] == ["gateway", "call"]:
        method = args[2]
        params = json.loads(flag("--params", "{}"))
        if method == "sessions.list":
            return {"sessions": [{"hasActiveRun": state.get("busy", False)}], "hasMore": state.get("truncated", False)}
        if method == "cron.list":
            jobs = list(state.get("jobs", {}).values())
            return {"jobs": jobs, "hasMore": False}
        if method == "astra.replyGuard.status":
            cfg = state.get("loaded_config", {}).get("plugins", {}).get("entries", {}).get("astra-reply-resilience", {}).get("config", {})
            return {"ownerConfigured": bool(cfg.get("ownerIds")), "instagramJobId": cfg.get("instagramJobId", ""),
                    "messagingGuard": {"storageAvailable": True}}
        if method == "astra.messagingGuard.setAwayWindow":
            state["window"] = {"id": params["windowId"], "expiresAt": params["expiresAt"]}
            return {"applied": True, "window": state["window"]}
        if method == "astra.messagingGuard.status":
            window = state.get("window")
            if window:
                window = {**window, "expired": window["expiresAt"] <= time.time() * 1000}
            return {"storageAvailable": True, "paused": state.get("paused", {}), "awayReply": {"window": window}}
        if method in ("astra.messagingGuard.pause", "astra.messagingGuard.resume", "astra.messagingGuard.reportRestriction"):
            paused = state.setdefault("paused", {})
            if method.endswith("resume"):
                if not params.get("reviewed"):
                    return {"applied": False}
                paused.pop(params["platform"], None)
            else:
                paused[params["platform"]] = {"code": params.get("code", "OPERATOR_PAUSED")}
            return {"applied": True}
        if method == "web.login.start":
            return {"message": "Synthetic QR placeholder; no real account", "qrDataUrl": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK7sAAAAASUVORK5CYII="}
        if method == "web.login.wait":
            return {"connected": True, "message": "Synthetic link only"}
        if method == "channels.status":
            return {"channels": {"whatsapp": {"linked": True, "connected": False, "lastError": state.get("channel_error", "ECONNRESET")}}}
    if args[:1] == ["gateway"] and args[1] in ("install", "start", "stop", "restart"):
        if args[1] in ("start", "restart"):
            state["loaded_config"] = state.get("config", {})
        return "Synthetic gateway service operation"
    if args[:1] == ["cron"]:
        jobs = state.setdefault("jobs", {})
        if args[1] == "list":
            return {"jobs": list(jobs.values()), "hasMore": False}
        if args[1] == "add":
            identifier = f"synthetic-job-{state.get('sequence', 0) + 1}"
            state["sequence"] = state.get("sequence", 0) + 1
            jobs[identifier] = {"id": identifier, "enabled": "--disabled" not in args,
                "declarationKey": flag("--declaration-key"), "argv": json.loads(flag("--command-argv", "[]")),
                "cwd": flag("--command-cwd"), "target": flag("--to"), "at": flag("--at"),
                "every": flag("--every"), "cron": flag("--cron")}
            if state.pop("lose_add_reply", False):
                raise RuntimeError("Synthetic lost scheduler response")
            return jobs[identifier]
        identifier = args[2]
        if identifier not in jobs:
            raise RuntimeError("job not found")
        if args[1] in ("enable", "disable"):
            jobs[identifier]["enabled"] = args[1] == "enable"
            return {"ok": True}
        if args[1] == "edit":
            jobs[identifier]["at"] = flag("--at")
            if state.pop("lose_edit_reply", False):
                raise RuntimeError("Synthetic lost edit response")
            return {"ok": True}
    if args[:1] == ["browser"]:
        profiles = state.setdefault("profiles", [])
        if args[1] == "profiles":
            return {"profiles": [{"name": name} for name in profiles]}
        if args[1] == "create-profile":
            profiles.append(flag("--name"))
            return {"ok": True}
        assert flag("--browser-profile") == "instagram"
        if args[3] == "open":
            assert args[4] == "https://www.instagram.com/direct/inbox/"
        return {"ok": True, "message": "Fake browser only; no navigation performed"}
    raise RuntimeError(f"Unimplemented fake operation: {tool} {args}")


if __name__ == "__main__":
    raise SystemExit(main())
