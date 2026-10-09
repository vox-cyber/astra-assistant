"""Real CLI/HTTP/filesystem workflows against strict fake subprocess tools."""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import threading
import time
import unittest
from unittest.mock import patch
from sandbox_support import Sandbox


@unittest.skipUnless(os.environ.get("ASTRA_OS_SANDBOX") == "1", "Run scripts/run_sandbox.py for the network/filesystem-isolated suite")
class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.s = Sandbox()
        self.addCleanup(self.s.close)
        self.addCleanup(self.s.assert_contained)

    def test_fresh_install_model_check_apply_and_restart_persist_across_processes(self):
        self.s.setup()
        self.assertTrue(self.s.cli("health")["ready"])
        status = self.s.cli("status")
        self.assertTrue(status["settings"]["runtime_configured"])
        self.assertNotIn("provider_api_key", status["settings"])
        self.assertTrue(self.s.cli("model-check")["selected_model_present"])
        self.assertTrue(self.s.cli("model-check", "--completion")["completion_verified"])
        self.s.cli("gateway", "restart")
        self.assertTrue(self.s.cli("health")["ready"])
        calls = self.s.native()["calls"]
        installs = [c for c in calls if c["tool"] == "npm"]
        self.assertEqual(len(installs), 1)
        self.assertNotIn("-g", installs[0]["args"])
        self.assertEqual(len(self.s.http_calls), 2)
        self.assertEqual((self.s.data / "private/settings.json").stat().st_mode & 0o777, 0o600)

    def test_reusing_existing_tools_reports_actual_versions_and_rejects_version_drift(self):
        self.s.cli("bootstrap")
        self.s.control(router_version="3.8.50")
        self.assertIn("3.8.50", self.s.cli("bootstrap")["omniroute"])
        self.s.control(core_version="OpenClaw 2099.1.0")
        self.assertIn("version", self.s.cli("bootstrap", success=False).lower())

    def test_invalid_schema_busy_sessions_and_wrong_node_stop_setup(self):
        self.s.cli("configure", data={"owner_name": "Sandbox", "owner_phone": "+15555550100"})
        self.s.cli("bootstrap")
        self.s.control(invalid_schema=True)
        self.s.cli("apply", success=False)
        self.assertNotIn("config", self.s.native())
        self.assertFalse(self.s.cli("status")["settings"]["runtime_configured"])
        self.s.control(invalid_schema=False)
        self.s.cli("apply")
        self.s.control(busy=True)
        self.s.cli("gateway", "restart", success=False)
        self.assertFalse(any(c["args"][2:4] == ["gateway", "restart"] for c in self.s.native()["calls"]))

    def test_reminder_lifecycle_runs_real_worker_without_transport(self):
        self.s.setup()
        task = self.s.cli("task", "create", "Synthetic reminder", "--at", "20m")
        job = self.s.native()["jobs"][task["job_id"]]
        self.assertEqual(job["target"], "+15555550100")
        result = subprocess.run(job["argv"], cwd=job["cwd"], env=self.s.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Synthetic reminder", result.stdout)
        self.s.cli("task", "postpone", task["id"], "--at", "40m")
        self.s.cli("task", "complete", task["id"])
        self.assertFalse(self.s.native()["jobs"][task["job_id"]]["enabled"])
        self.assertEqual(self.s.cli("remind", task["id"], raw=True).strip(), "")

    def test_lost_creation_reply_reconciles_without_duplicate_job(self):
        self.s.setup()
        self.s.control(lose_add_reply=True)
        task = self.s.cli("task", "create", "Response lost", "--at", "20m")
        self.assertEqual(task["status"], "active")
        self.assertEqual(len(self.s.native()["jobs"]), 1)

    def test_lost_postpone_reply_is_uncertain_and_cannot_reenable_old_schedule(self):
        self.s.setup()
        task = self.s.cli("task", "create", "Postpone uncertain", "--at", "20m")
        self.s.control(lose_edit_reply=True)
        self.s.cli("task", "postpone", task["id"], "--at", "40m", success=False)
        record = self.s.cli("task", "show", task["id"])
        self.assertEqual(record["status"], "uncertain")
        reconciled = self.s.cli("task", "reconcile", task["id"])
        self.assertEqual(reconciled["status"], "active")
        self.assertEqual(reconciled["job_id"], task["job_id"])

    def test_instagram_create_restart_enable_disable_and_timed_expiry(self):
        self.s.setup()
        result = self.s.cli("instagram", "watch-create")
        job = result["job_id"]
        self.assertFalse(self.s.native()["jobs"][job]["enabled"])
        self.s.cli("instagram", "watch-enable", success=False)
        self.s.cli("gateway", "restart")
        self.s.cli("instagram", "watch-enable")
        self.assertTrue(self.s.native()["jobs"][job]["enabled"])
        window = self.s.cli("away-for", "--hours", "5")
        self.s.cli("away-expire", "a-stale-window")
        self.assertTrue(self.s.native()["jobs"][job]["enabled"])
        self.s.control(window={"id": window["window_id"], "expiresAt": 1})
        self.s.cli("away-expire", window["window_id"])
        self.assertFalse(self.s.native()["jobs"][job]["enabled"])

    def test_instagram_disable_with_no_job_has_no_creation_side_effect(self):
        self.s.setup()
        self.s.cli("instagram", "watch-disable")
        self.assertEqual(self.s.native().get("jobs", {}), {})

    def test_google_fake_consent_history_style_phone_notes_and_services(self):
        self.s.setup()
        client = self.s.root / "synthetic-client.json"
        client.write_text(json.dumps({"installed": {"client_id": "synthetic-client", "client_secret": "synthetic-only"}}))
        self.s.cli("google", "import-client", str(client))
        self.assertFalse(self.s.cli("google", "status")["authorized"])
        self.assertTrue(self.s.cli("google", "login")["authorized"])
        self.s.cli("google", "run", "drive", "ls", "--max", "1", "--json")
        self.s.cli("history", "messages", "search", "synthetic")
        self.assertEqual(self.s.cli("persona", "collect", "--before", "2021-01-01")["samples"], 8)
        self.assertFalse(self.s.cli("persona", "status")["profile_ready"])
        self.assertIn("SYNTHETIC-DEVICE", self.s.cli("phone", "status")["text"])
        self.s.cli("phone", "screen", "--serial", "SYNTHETIC-DEVICE")
        self.assertTrue(Path(self.s.cli("notes-init")["path"]).is_relative_to(self.s.home))
        event = self.s.cli("calendar-export", "--title", "Synthetic event", "--start", "2030-01-01T09:00:00Z", "--end", "2030-01-01T10:00:00Z")
        self.assertTrue(Path(event["path"]).is_relative_to(self.s.data))
        self.s.cli("services-install")
        units = self.s.home / ".config/systemd/user"
        self.assertEqual(len(list(units.glob("astra-community-*.service"))), 4)

    def test_failed_model_and_failed_agent_are_not_reported_as_success(self):
        self.s.setup()
        self.s.model_reply = "NOT READY"
        self.s.cli("model-check", "--completion", success=False)
        self.s.control(agent_failure=True)
        self.assertIn("Some actions may have run", self.s.cli("ask", "Synthetic failure", success=False))

    def test_private_backup_is_contained_and_excludes_outside_symlinks(self):
        self.s.setup()
        (self.s.data / "escape").symlink_to("/etc")
        result = self.s.cli("backup")
        path = Path(result["path"])
        self.assertTrue(path.is_relative_to(self.s.home))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with tarfile.open(path) as archive:
            self.assertFalse(any("escape" in name for name in archive.getnames()))
            self.assertIn("astra/private/settings.json", archive.getnames())

    def test_router_environment_separates_all_listeners_and_inherited_credentials(self):
        self.s.cli("bootstrap")
        self.s.cli("router", "start")
        env = next(c["env"] for c in self.s.native()["calls"] if c["tool"] == "omniroute" and "serve" in c["args"])
        self.assertEqual(env["OMNIROUTE_SERVER_HOST"], "127.0.0.1")
        self.assertEqual(env["LIVE_WS_PORT"], "20133")
        self.assertEqual(env["EMBED_WS_PROXY_PORT"], "20134")

    def test_network_namespace_has_no_external_route_and_no_live_home(self):
        self.assertFalse(Path("/home").exists())
        with socket.socket() as sock:
            sock.settimeout(.1)
            with self.assertRaises(OSError):
                sock.connect(("192.0.2.1", 443))
        for port in (18789, 18791, 20128, 20129, 8765):
            with socket.socket() as sock:
                sock.settimeout(.1)
                self.assertNotEqual(sock.connect_ex(("127.0.0.1", port)), 0)

    def test_dashboard_real_actions_and_auth_against_fake_native_tools(self):
        from astra_app.server import Dashboard
        with patch.dict(os.environ, self.s.env, clear=True):
            server = Dashboard(("127.0.0.1", 0), "synthetic-http-key")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def request(method, path, body=None, auth=True):
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=15)
                    headers = {"Content-Type": "application/json"}
                    if auth:
                        headers["Authorization"] = "Bearer synthetic-http-key"
                    conn.request(method, path, json.dumps(body) if body else None, headers)
                    response = conn.getresponse()
                    value, status = json.loads(response.read()), response.status
                    conn.close()
                    return status, value

                def action(name, params=None):
                    status, value = request("POST", "/api/actions", {"action": name, "params": params or {}})
                    self.assertEqual(status, 202)
                    for _ in range(200):
                        result = request("GET", "/api/jobs/" + value["id"])[1]
                        if result["state"] != "running":
                            self.assertEqual(result["state"], "completed", result)
                            return result["result"]
                        time.sleep(.025)
                    self.fail("Dashboard job did not finish")

                self.assertEqual(request("GET", "/api/status", auth=False)[0], 403)
                action("settings.save", {"owner_name": "Sandbox", "owner_phone": "+15555550100",
                    "instagram_username": "synthetic_account", "provider_url": self.s.url})
                action("bootstrap")
                action("runtime.apply")
                action("gateway.start")
                self.assertTrue(action("health")["ready"])
                self.assertTrue(action("model.test")["completion_verified"])
                watcher = action("instagram.create")
                self.assertTrue(watcher["job_id"])
                self.assertEqual(action("instagram.disable")["job_id"], watcher["job_id"])
                self.assertIn("qrDataUrl", action("whatsapp.link"))
                self.assertTrue(action("whatsapp.wait")["connected"])
                task = action("tasks.create", {"title": "HTTP reminder", "at": "20m"})
                self.assertEqual(action("tasks.cancel", {"id": task["id"]})["status"], "cancelled")
                self.assertIn("Synthetic answer", action("ask", {"prompt": "Fake task"})["text"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
