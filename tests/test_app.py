import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from astra_app import settings, runtime, google, integrations, notes, workers, persona
from astra_app.commands import Runner, OperationError, require_idle, redact


class LocalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="astra-test-")
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {"ASTRA_HOME": self.temp.name + "/data"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        settings.save({"owner_name": "Test Owner", "owner_phone": "+15555550100"})


class SettingsTests(LocalTest):
    def test_private_atomic_settings_and_redacted_view(self):
        settings.save({"provider_api_key": "unit-test-only-key"})
        self.assertNotIn("provider_api_key", settings.public())
        self.assertTrue(settings.public()["provider_key_configured"])
        self.assertEqual(settings.settings_path().stat().st_mode & 0o777, 0o600)
        self.assertEqual(settings.settings_path().parent.stat().st_mode & 0o777, 0o700)
        settings.save({"provider_api_key": ""})
        self.assertEqual(settings.load()["provider_api_key"], "unit-test-only-key")
        self.assertNotIn("unit-test-only-key", redact("Authorization: Bearer unit-test-only-key"))

    def test_validation_rejects_bad_types_identities_and_urls(self):
        for value in ({"fallback_models": None}, {"owner_phone": "local-number"}, {"delegates": ["a name"]},
                      {"timezone": "not/a/timezone"}, {"away_quiet_minutes": True},
                      {"provider_url": "https://name:password@example.invalid/v1"}, {"runtime_configured": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings.save(value)

    def test_private_home_cannot_be_inside_checkout(self):
        with patch.dict(os.environ, {"ASTRA_HOME": str(settings.PROJECT / "private")}), self.assertRaises(ValueError):
            settings.home()

    def test_settings_corruption_is_not_silently_reset(self):
        settings.settings_path().write_text("not JSON")
        with self.assertRaises(ValueError):
            settings.load()


class CommandTests(LocalTest):
    def test_openclaw_profile_and_inherited_config_overrides_are_isolated(self):
        env = {"OPENCLAW_CONFIG_PATH": "/wrong/config", "OPENCLAW_HOME": "/wrong/home", "OPENCLAW_GATEWAY_URL": "ws://wrong.invalid", "OPENCLAW_GATEWAY_TOKEN": "unit-test-only"}
        with patch.dict(os.environ, env), patch("astra_app.commands.executable", return_value="/fake/openclaw"), \
             patch("astra_app.commands.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")) as process:
            Runner().json("openclaw", ["gateway", "call", "status", "--json"])
            args = process.call_args.args[0]
            self.assertEqual(args[:3], ["/fake/openclaw", "--profile", "astra-community"])
            self.assertNotIn("OPENCLAW_CONFIG_PATH", process.call_args.kwargs["env"])
            self.assertNotIn("OPENCLAW_HOME", process.call_args.kwargs["env"])
            self.assertNotIn("OPENCLAW_GATEWAY_URL", process.call_args.kwargs["env"])
            self.assertNotIn("OPENCLAW_GATEWAY_TOKEN", process.call_args.kwargs["env"])

    def test_uncertain_process_timeout_never_retries(self):
        with patch("astra_app.commands.executable", return_value="/fake/tool"), \
             patch("astra_app.commands.subprocess.run", side_effect=subprocess.TimeoutExpired("tool", 1)) as process:
            with self.assertRaisesRegex(OperationError, "uncertain"):
                Runner().run("tool")
            self.assertEqual(process.call_count, 1)

    def test_idle_gate_includes_queued_subagents_and_truncated_responses(self):
        from unittest.mock import Mock
        for reply in ({"sessions": [{"hasActiveSubagentRun": True}]}, {"sessions": [{"status": "queued"}]},
                      {"sessions": [{"activeRunIds": ["synthetic-run"]}]},
                      {"sessions": [], "hasMore": True}, {"sessions": [{}] * 1000}, {}):
            with self.subTest(reply=reply), self.assertRaises(OperationError):
                require_idle(Mock(json=lambda *a: reply))


class RuntimeTests(LocalTest):
    def test_patch_is_user_configured_and_cannot_enable_unknown_commands(self):
        settings.save({"delegates": ["+15555550101"], "away_enabled": True})
        with patch("astra_app.runtime.executable", return_value="/fake/openclaw"):
            value = runtime.patch()
        self.assertEqual(value["gateway"]["port"], 18791)
        self.assertEqual(value["channels"]["whatsapp"]["allowFrom"], ["*"])
        self.assertEqual(value["commands"]["ownerAllowFrom"], ["+15555550100", "+15555550101"])
        plugin = value["plugins"]["entries"][runtime.PLUGIN]["config"]
        self.assertEqual(plugin["profile"], "astra-community")
        self.assertIn("Test Owner", plugin["awayText"])
        self.assertNotIn(".openclaw/media", plugin["inboundDir"])

    def test_core_bootstrap_uses_private_prefix_and_pinned_versions(self):
        from unittest.mock import Mock
        target = settings.home() / "tools/node_modules/.bin"
        target.mkdir(parents=True)
        for name in ("openclaw", "omniroute"):
            path = target / name
            path.write_text("#!/bin/sh\n")
            path.chmod(0o700)
        runner = Mock(run=Mock(side_effect=["v24.21.0", "installed"]))
        result = runtime.bootstrap(runner)
        args = runner.run.call_args_list[1].args[1]
        self.assertIn("--prefix", args)
        self.assertEqual(args[args.index("--prefix") + 1], str(settings.home() / "tools"))
        self.assertIn("openclaw@2026.9.1", args)
        self.assertIn("omniroute@3.8.51", args)
        self.assertIn(str(settings.home() / "tools"), result["tools"])

    def test_private_core_status_does_not_accept_another_global_installation(self):
        from unittest.mock import Mock
        with patch("astra_app.integrations.executable", return_value="/global/tool"), patch("astra_app.integrations.runtime.local_executable", side_effect=OperationError("private core missing")):
            state = integrations.inspect()
        self.assertEqual(state["private_core"], {"openclaw": False, "omniroute": False})

    def test_workspace_preserves_owner_edits(self):
        root = runtime.initialize_workspace()
        (root / "SOUL.md").write_text("Owner customization")
        runtime.initialize_workspace()
        self.assertEqual((root / "SOUL.md").read_text(), "Owner customization")

    def test_wrong_core_version_cannot_install_or_apply(self):
        from unittest.mock import Mock
        local = settings.home() / "tools/node_modules/.bin"
        local.mkdir(parents=True)
        (local / "openclaw").write_text("#!/bin/sh\n")
        runner = Mock(run=Mock(return_value="2026.9.10"))
        with self.assertRaises(OperationError):
            runtime.apply(runner)
        self.assertEqual(runner.run.call_count, 1)

    def test_ask_does_not_treat_missing_final_as_success(self):
        from unittest.mock import Mock
        cfg = settings.load(); cfg["runtime_configured"] = True
        settings.write_private(settings.settings_path(), cfg)
        with self.assertRaisesRegex(OperationError, "Some actions may have run"):
            runtime.ask("Inspect a folder", Mock(json=lambda *a, **k: {"status": "ok", "result": {"payloads": []}}))

    def test_failed_schema_preview_never_applies_configuration(self):
        from unittest.mock import Mock
        runner = Mock(run=Mock(return_value="OpenClaw 2026.9.1"), json=Mock(return_value={"ok": False, "checks": {"schema": False}}))
        with patch("astra_app.runtime.local_executable", return_value=Path("/fake/openclaw")), \
             patch("astra_app.runtime.executable", return_value="/fake/openclaw"), self.assertRaisesRegex(OperationError, "validation did not pass"):
            runtime.apply(runner)
        calls = [call.args[1] for call in runner.run.call_args_list]
        self.assertNotIn(["config", "patch", "--stdin"], calls)
        self.assertFalse(settings.load()["runtime_configured"])


class IntegrationTests(LocalTest):
    def test_google_home_and_environment_do_not_inherit_another_account_token(self):
        settings.save({"google_email": "owner@example.invalid"})
        with patch.dict(os.environ, {"GOG_ACCESS_TOKEN": "unit-test-only", "GOG_HOME": "/wrong"}):
            environment = google.environment()
        self.assertNotIn("GOG_ACCESS_TOKEN", environment)
        self.assertEqual(environment["GOG_HOME"], str(settings.home() / "private/google"))
        self.assertEqual(environment["GOG_ACCOUNT"], "owner@example.invalid")
        self.assertEqual((settings.home() / "private/google/keyring-password").stat().st_mode & 0o777, 0o600)

    def test_notes_do_not_overwrite_existing_content(self):
        with patch("astra_app.notes.vault", return_value=Path(self.temp.name) / "Notes"):
            notes.initialize()
            (notes.vault() / "Home.md").write_text("Existing note")
            notes.initialize()
            self.assertEqual((notes.vault() / "Home.md").read_text(), "Existing note")

    def test_calendar_requires_timezone_and_escapes_line_injection(self):
        with self.assertRaises(OperationError):
            notes.event("Title", "2030-01-01T10:00:00", "2030-01-01T11:00:00")
        result = notes.event("Plan\nATTENDEE:fake", "2030-01-01T10:00:00+01:00", "2030-01-01T11:00:00+01:00")
        body = Path(result["path"]).read_text()
        self.assertIn("DTSTART:20300101T090000Z", body)
        self.assertNotIn("\nATTENDEE:", body)

    def test_history_cannot_send_and_uses_private_store(self):
        from unittest.mock import Mock
        runner = Mock(run=Mock(return_value="history"))
        with self.assertRaises(OperationError):
            integrations.history(["messages", "send"], runner)
        integrations.history(["messages", "search", "project"], runner)
        self.assertIn("--read-only", runner.run.call_args.args[1])
        self.assertIn(str(settings.home() / "private/wacli"), runner.run.call_args.args[1])

    def test_recovery_preserves_restrictions_and_unknown_state(self):
        from unittest.mock import Mock
        for error, expected in (("challenge_required", "restricted"), ("unknown failure", "unclassified_disconnect")):
            responses = iter([{"storageAvailable": True, "paused": {}},
                              {"channels": {"whatsapp": {"linked": True, "connected": False, "lastError": error}}}, {}])
            runner = Mock(json=lambda *a: next(responses), run=Mock())
            self.assertEqual(workers.recover_once(runner), expected)
            runner.run.assert_not_called()

    def test_style_cutoff_cannot_include_post_setup_generated_messages(self):
        from unittest.mock import Mock
        runtime.initialize_workspace()
        runner = Mock()
        with self.assertRaises(OperationError):
            persona.collect("2099-01-01", runner)
        runner.json.assert_not_called()
