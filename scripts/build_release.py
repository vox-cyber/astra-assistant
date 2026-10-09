#!/usr/bin/env python3
"""Build and inspect a source-only release; never copy runtime directories."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOP = {"README.md", "LICENSE", ".gitignore", "pyproject.toml", "launch.py", "start.sh"}
FOLDERS = {"astra_app", "plugins", "config", "docs", "examples", "tests", "scripts", ".github"}
EXTENSIONS = {".py", ".js", ".mjs", ".json", ".html", ".css", ".md", ".yml", ".yaml", ".sh"}
SKIP = {"__pycache__", "node_modules", ".venv", "dist", "build", ".git", ".pytest_cache"}
SENSITIVE = re.compile(r"(^|/)(?:private|credentials|secrets|history|profiles|media|logs|state)(/|$)|(?:client_secret|token|creds|openclaw\.json|\.private\.)", re.I)
SECRETS = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAIza[\w-]{35}\b|\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b|\bGOCSPX-[A-Za-z0-9_-]{20,}\b")


def files():
    found = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in SKIP or part.endswith(".egg-info") for part in relative.parts):
            continue
        eligible = str(relative) in TOP or relative.parts[0] in FOLDERS
        if not eligible:
            continue
        if path.is_symlink():
            raise ValueError(f"Release refuses symlink: {relative}")
        if path.is_file():
            if relative.parts[0] == "config" and relative.as_posix() != "config/settings.example.json":
                raise ValueError(f"Unexpected configuration file requires review: {relative}")
            if SENSITIVE.search(relative.as_posix()) or path.suffix in {".pem", ".key", ".sqlite", ".db", ".log", ".p12", ".pfx"}:
                raise ValueError(f"Sensitive artifact path: {relative}")
            if str(relative) in TOP or path.suffix in EXTENSIONS:
                found.append(path)
    return sorted(found)


def scan(paths, denied=()):
    problems = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(ROOT)
        if SECRETS.search(text):
            problems.append(f"Potential secret pattern: {name}")
        if any(value and value.casefold() in text.casefold() for value in denied):
            problems.append(f"Private identifier match: {name}")
    example = json.loads((ROOT / "config/settings.example.json").read_text())
    for key in ("owner_name", "owner_phone", "owner_lid", "provider_api_key", "google_email", "google_client_file", "instagram_username"):
        if example.get(key):
            problems.append(f"Example must have an empty {key}")
    if example.get("delegates"):
        problems.append("Example delegates must be empty")
    if problems:
        raise ValueError("\n".join(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--deny-file", type=Path)
    args = parser.parse_args()
    try:
        denied = args.deny_file.read_text().splitlines() if args.deny_file else []
        paths = files(); scan(paths, denied)
        print(f"Release scan passed: {len(paths)} source/template files; no runtime stores included.")
        if not args.check:
            folder = ROOT / "dist"
            folder.mkdir(exist_ok=True)
            target = folder / "astra-assistant-v0.1.0.zip"
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in paths:
                    name = "astra-assistant/" + path.relative_to(ROOT).as_posix()
                    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = (0o100755 if path.name == "start.sh" else 0o100644) << 16
                    archive.writestr(info, path.read_bytes())
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            target.with_suffix(".zip.sha256").write_text(digest + "  " + target.name + "\n")
            print(f"Created {target.relative_to(ROOT)} ({target.stat().st_size} bytes)")
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
