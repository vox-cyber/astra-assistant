#!/usr/bin/env python3
"""Run real application flows in a disposable Linux filesystem/network namespace."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default="/usr/bin/python3", help="Interpreter inside the read-only /usr mount")
    args = parser.parse_args()
    binary = shutil.which("bwrap")
    if not binary:
        raise SystemExit("Install bubblewrap to run the OS-isolated sandbox. No fallback to real account tools is allowed.")
    with tempfile.TemporaryDirectory(prefix="astra-os-sandbox-") as temporary:
        command = [binary, "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--ro-bind", str(ROOT), "/app", "--bind", temporary, "/sandbox",
            "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/sandbox",
            "--setenv", "TMPDIR", "/sandbox", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--setenv", "ASTRA_OS_SANDBOX", "1", "--chdir", "/app",
            args.python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_sandbox.py", "-v"]
        result = subprocess.run(command, timeout=180)
    if result.returncode == 0:
        print("OS sandbox passed and removed: private filesystem/network, fake accounts/tools, no host services reachable.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
