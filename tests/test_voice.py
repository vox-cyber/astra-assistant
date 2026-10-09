import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

path = Path(__file__).resolve().parents[1] / "plugins/astra-reply-resilience/voice-player.py"
spec = importlib.util.spec_from_file_location("voice_player", path)
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="astra-voice-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "inbound"
        self.root.mkdir()
        self.clip = self.root / "clip.ogg"
        self.clip.write_bytes(b"synthetic audio")

    def test_media_cannot_escape_inbound_directory_through_path_or_symlink(self):
        outside = Path(self.temp.name) / "outside.ogg"
        outside.write_bytes(b"synthetic")
        link = self.root / "link.ogg"
        link.symlink_to(outside)
        for path in (outside, link):
            with self.assertRaises(ValueError):
                voice.validate_path(path, self.root)

    def test_duplicate_persisted_id_is_not_enqueued_again(self):
        db_path = Path(self.temp.name) / "queue.sqlite"
        with voice.connect(db_path) as db:
            self.assertEqual(voice.enqueue(db, "message-one", self.clip, self.root)["status"], "queued")
        with voice.connect(db_path) as db:
            self.assertEqual(voice.enqueue(db, "message-one", self.clip, self.root)["status"], "duplicate")

    def test_queue_is_bounded_to_ten_pending_clips(self):
        with voice.connect(Path(self.temp.name) / "queue.sqlite") as db:
            for i in range(10):
                self.assertEqual(voice.enqueue(db, str(i), self.clip, self.root)["status"], "queued")
            self.assertEqual(voice.enqueue(db, "overflow", self.clip, self.root)["status"], "queue_full")

    def test_audio_settings_restore_even_when_setup_fails(self):
        sink = {"name": "synthetic-sink", "active_port": "old-port", "mute": True,
                "volume": {"left": {"value": 32768}, "right": {"value": 32768}},
                "ports": [{"name": "analog-output-speaker", "type": "speaker", "availability": "available"}]}
        calls = []
        def run(args):
            calls.append(args)
            if "list" in args:
                return json.dumps([sink])
            if args[-1] == "90%":
                raise subprocess.CalledProcessError(1, args)
            return ""
        with patch.object(voice, "run", side_effect=run), patch.object(voice.subprocess, "Popen") as player:
            with self.assertRaises(subprocess.CalledProcessError):
                voice.play(self.clip, self.root)
            player.assert_not_called()
        self.assertIn(["pactl", "set-sink-volume", "synthetic-sink", "32768", "32768"], calls)
        self.assertIn(["pactl", "set-sink-mute", "synthetic-sink", "1"], calls)
        self.assertIn(["pactl", "set-sink-port", "synthetic-sink", "old-port"], calls)
