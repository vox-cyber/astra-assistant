#!/usr/bin/env python3
"""Bounded local speaker queue. No AI, credential access or network playback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
import fcntl

STOP = False


def validate_path(raw, root):
    path, root = Path(raw).resolve(strict=True), Path(root).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("audio_path_outside_inbound_store")
    if path.suffix.lower() not in (".ogg", ".opus", ".mp3", ".m4a", ".wav", ".aac", ".flac", ".webm") or not 0 < path.stat().st_size <= 25 * 1024 * 1024:
        raise ValueError("unsupported_audio_or_size")
    return path


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path, timeout=5)
    path.chmod(0o600)
    connection.execute("CREATE TABLE IF NOT EXISTS jobs (seq INTEGER PRIMARY KEY, key TEXT UNIQUE, path TEXT, status TEXT, error TEXT, created REAL)")
    connection.commit()
    return connection


def enqueue(db, identifier, path, root):
    if not isinstance(identifier, str) or not 1 <= len(identifier) <= 256:
        raise ValueError("invalid_message_id")
    key = hashlib.sha256(("owner-self-chat:" + identifier).encode()).hexdigest()
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute("SELECT 1 FROM jobs WHERE key=?", (key,)).fetchone():
            db.commit(); return {"status": "duplicate"}
        checked = validate_path(path, root)
        if db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','playing')").fetchone()[0] >= 10:
            db.rollback(); return {"status": "queue_full"}
        db.execute("INSERT INTO jobs(key,path,status,created) VALUES(?,?,?,?)", (key, str(checked), "queued", time.time()))
        db.commit(); return {"status": "queued", "volume_percent": 90}
    except Exception:
        db.rollback(); raise


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=3).stdout


def play(raw, root):
    path = validate_path(raw, root)
    sinks = json.loads(run(["pactl", "--format=json", "list", "sinks"]))
    selected = next(((sink, port["name"]) for sink in sinks for port in sink.get("ports", [])
                     if ("speaker" in str(port.get("type", "")).lower() or port["name"] == "analog-output-speaker")
                     and port.get("availability") != "not available"), None)
    if not selected:
        raise ValueError("laptop_speakers_unavailable")
    sink, port = selected
    name, old_port = sink["name"], sink.get("active_port")
    if isinstance(old_port, dict):
        old_port = old_port.get("name")
    volumes = [str(channel["value"]) for channel in sink.get("volume", {}).values()]
    mute, player = "1" if sink.get("mute") else "0", None
    try:
        for args in (["pactl", "set-sink-port", name, port], ["pactl", "set-sink-volume", name, "90%"], ["pactl", "set-sink-mute", name, "0"]):
            run(args)
        player = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-threads", "1",
                                   "-protocol_whitelist", "file,pipe", "-i", str(path)],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  env=dict(os.environ, SDL_AUDIODRIVER="pulseaudio", PULSE_SINK=name))
        deadline = time.monotonic() + 600
        while player.poll() is None:
            if STOP or time.monotonic() >= deadline:
                raise TimeoutError("playback_interrupted")
            time.sleep(0.1)
        if player.returncode:
            raise RuntimeError("audio_decoder_or_output_failed")
    finally:
        if player is not None and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=2)
            except subprocess.TimeoutExpired:
                player.kill(); player.wait()
        restore = ([['pactl', 'set-sink-volume', name, *volumes]] if volumes else []) + [["pactl", "set-sink-mute", name, mute]]
        if old_port:
            restore.append(["pactl", "set-sink-port", name, old_port])
        for args in restore:
            try:
                run(args)
            except (OSError, subprocess.SubprocessError):
                pass


def worker(db, root):
    signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__("STOP", True))
    signal.signal(signal.SIGINT, lambda *_: globals().__setitem__("STOP", True))
    db.execute("UPDATE jobs SET status='interrupted',error='worker_restarted' WHERE status='playing'")
    db.commit()
    while not STOP:
        db.execute("BEGIN IMMEDIATE")
        job = db.execute("SELECT seq,path FROM jobs WHERE status='queued' ORDER BY seq LIMIT 1").fetchone()
        if job:
            db.execute("UPDATE jobs SET status='playing' WHERE seq=?", (job[0],))
        db.commit()
        if not job:
            time.sleep(0.5); continue
        status, error = "played", None
        try:
            play(job[1], root)
        except Exception as exc:
            status, error = "failed", type(exc).__name__
        db.execute("UPDATE jobs SET status=?,error=? WHERE seq=?", (status, error, job[0]))
        db.commit()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["enqueue", "worker", "status"])
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--inbound-dir", default=str(Path.home() / ".openclaw-astra-community/media/inbound"))
    parser.add_argument("--message-id")
    parser.add_argument("--path")
    args = parser.parse_args()
    with connect(Path(args.state_dir) / "queue.sqlite") as db:
        if args.mode == "worker":
            with (Path(args.state_dir) / "worker.lock").open("a+") as lock:
                os.chmod(lock.name, 0o600)
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError("worker_already_running")
                worker(db, args.inbound_dir)
        elif args.mode == "status":
            print(json.dumps({"volume_percent": 90, "counts": dict(db.execute("SELECT status,count(*) FROM jobs GROUP BY status"))}))
        else:
            print(json.dumps(enqueue(db, args.message_id, args.path, args.inbound_dir)))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"status": "failed", "error": type(error).__name__}))
        raise SystemExit(1)
