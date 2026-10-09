import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from astra_app import settings
from astra_app.server import Dashboard, Jobs
from astra_app.commands import OperationError


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="astra-http-")
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"ASTRA_HOME": self.temp.name})
        env.start(); self.addCleanup(env.stop)
        settings.save({"provider_api_key": "unit-test-only-secret"})
        self.calls = []
        def action(name, params):
            self.calls.append((name, params))
            return {"message": "Synthetic operation result"}
        self.server = Dashboard(("127.0.0.1", 0), "synthetic-dashboard-secret", Jobs(action))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown(); self.server.server_close()

    def request(self, method, path, body=None, authenticated=True, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        base = {"Content-Type": "application/json"}
        if authenticated:
            base["Authorization"] = "Bearer synthetic-dashboard-secret"
        base.update(headers or {})
        client.request(method, path, body=json.dumps(body) if body is not None else None, headers=base)
        response = client.getresponse()
        payload, status, reply_headers = response.read(), response.status, dict(response.getheaders())
        client.close()
        return status, payload, reply_headers

    def test_api_needs_auth_and_rejects_remote_host_origin(self):
        for authenticated, headers in ((False, {}), (True, {"Origin": "https://attacker.invalid"}),
                                        (True, {"Host": "attacker.invalid"})):
            status, _, _ = self.request("GET", "/api/status", authenticated=authenticated, headers=headers)
            self.assertEqual(status, 403)
        self.assertEqual(self.calls, [])

    def test_settings_endpoint_does_not_return_provider_secret(self):
        status, body, headers = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertNotIn(b"unit-test-only-secret", body)
        self.assertNotIn("provider_api_key", json.loads(body)["settings"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_static_assets_cannot_traverse_and_have_csp(self):
        status, body, headers = self.request("GET", "/", authenticated=False)
        self.assertEqual(status, 200)
        self.assertIn(b"Guided setup", body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET", "/../settings.py")[0], 404)
        self.assertEqual(self.request("GET", "/api/help?name=../settings.py")[0], 404)

    def test_action_job_reports_actual_completion(self):
        code, body, _ = self.request("POST", "/api/actions", {"action": "synthetic", "params": {"value": "sample"}})
        self.assertEqual(code, 202)
        identifier = json.loads(body)["id"]
        for _ in range(50):
            result = json.loads(self.request("GET", "/api/jobs/" + identifier)[1])
            if result["state"] != "running":
                break
            time.sleep(.01)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(self.calls, [("synthetic", {"value": "sample"})])

    def test_actions_reject_non_json_and_unauthorized_requests(self):
        value = {"action": "synthetic"}
        self.assertEqual(self.request("POST", "/api/actions", value, authenticated=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/actions", value, headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.calls, [])

    def test_job_serializer_blocks_concurrent_side_effects(self):
        entered, release = threading.Event(), threading.Event()
        def action(*_):
            entered.set(); release.wait(2)
        jobs = Jobs(action)
        jobs.submit("one", {})
        self.assertTrue(entered.wait(1))
        with self.assertRaises(OperationError):
            jobs.submit("two", {})
        release.set()

    def test_dispatcher_has_no_arbitrary_shell_operation(self):
        from astra_app.server import dispatch
        with self.assertRaises(OperationError):
            dispatch("exec", {"command": "untrusted command"})
