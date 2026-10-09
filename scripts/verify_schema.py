#!/usr/bin/env python3
"""Validate against installed OpenClaw with temporary HOME and dry-run only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from astra_app import settings, runtime
from astra_app.commands import executable


def main():
    original_home = Path.home()
    candidates = list((original_home / ".openclaw/npm/projects").glob("openclaw-whatsapp-*/node_modules/@openclaw/whatsapp"))
    binary = executable("openclaw")
    version = subprocess.run([binary, "--version"], capture_output=True, text=True, check=True).stdout
    if "2026.9.1" not in version:
        raise SystemExit("Install OpenClaw 2026.9.1 for this compatibility check")
    if not candidates:
        raise SystemExit("Pinned WhatsApp channel package is needed for its schema. Install it in a separate test profile first.")
    with tempfile.TemporaryDirectory(prefix="astra-schema-") as folder:
        root = Path(folder)
        os.environ["ASTRA_HOME"] = str(root / "astra")
        settings.save({"owner_name": "Test Owner", "owner_phone": "+15555550100"})
        value = runtime.patch()
        value["plugins"]["load"] = {"paths": [str(ROOT / "plugins/astra-reply-resilience"), str(candidates[0])]}
        value["plugins"]["allow"] = [runtime.PLUGIN, "whatsapp"]
        patch_path = root / "patch.json"
        settings.write_private(patch_path, value)
        env = dict(os.environ)
        for key in ("OPENCLAW_PROFILE", "OPENCLAW_STATE_DIR", "OPENCLAW_CONFIG_PATH", "OPENCLAW_HOME", "OPENCLAW_GATEWAY_PORT"):
            env.pop(key, None)
        env.update(HOME=str(root / "home"), OPENCLAW_STATE_DIR=str(root / "native"), OPENCLAW_CONFIG_PATH=str(root / "native/openclaw.json"))
        result = subprocess.run([binary, "config", "patch", "--file", str(patch_path), "--dry-run", "--json"], env=env,
                                text=True, capture_output=True, timeout=60)
        if result.returncode:
            print(result.stderr)
            print(result.stdout)
            return 1
        reply = json.loads(result.stdout)
        checks = reply.get("checks", {})
        if reply.get("ok") is not True or checks.get("schema") is not True or checks.get("resolvabilityComplete") is not True:
            print(json.dumps({"checks": checks, "errors": reply.get("errors")}, indent=2))
            return 1
        print("OpenClaw 2026.9.1 schema/resolvability passed in an isolated temporary HOME; no config apply, model call or send.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
