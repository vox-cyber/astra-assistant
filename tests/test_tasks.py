import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from astra_app import settings, tasks
from astra_app.commands import OperationError


class Scheduler:
    def __init__(self, uncertain=False):
        self.jobs, self.commands, self.uncertain = [], [], uncertain

    def json(self, name, args):
        self.commands.append(args)
        if args[:3] == ["gateway", "call", "cron.list"]:
            return {"jobs": self.jobs, "hasMore": False}
        action = args[1]
        if action == "add":
            declaration = args[args.index("--declaration-key") + 1]
            self.jobs.append({"id": "synthetic-job", "declarationKey": declaration})
            if self.uncertain:
                raise OperationError("response lost")
            return self.jobs[-1]
        if action == "list":
            return {"jobs": self.jobs}
        return {"ok": True}


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="astra-tasks-")
        self.addCleanup(self.temp.cleanup)
        environment = patch.dict(os.environ, {"ASTRA_HOME": self.temp.name})
        environment.start(); self.addCleanup(environment.stop)
        settings.save({"owner_phone": "+15555550100", "owner_name": "Test Owner"})

    def test_create_fixes_delivery_to_owner_and_uses_installed_module(self):
        runner = Scheduler()
        task = tasks.create("Test reminder", every="1h", assignee="Someone else", runner=runner)
        args = runner.commands[0]
        self.assertEqual(args[args.index("--to") + 1], "+15555550100")
        argv = json.loads(args[args.index("--command-argv") + 1])
        self.assertEqual(argv[1:4], ["-m", "astra_app", "remind"])
        self.assertEqual(task["status"], "active")
        self.assertIn("Repeats until", tasks.reminder(task["id"]))

    def test_lost_create_response_reconciles_once_without_duplicate(self):
        runner = Scheduler(uncertain=True)
        task = tasks.create("Test reminder", at="20m", runner=runner)
        self.assertEqual(task["job_id"], "synthetic-job")
        self.assertEqual(sum(args[1] == "add" for args in runner.commands), 1)

    def test_unreconciled_uncertainty_is_durable_and_not_retryable_as_active(self):
        runner = Mock(json=Mock(side_effect=OperationError("unavailable")))
        with self.assertRaises(OperationError):
            tasks.create("Test reminder", at="20m", runner=runner)
        task = tasks.list_tasks("all")[0]
        self.assertEqual(task["status"], "uncertain")
        with self.assertRaises(OperationError):
            tasks.finish(task["id"], "completed", runner)

    def test_complete_cancels_scheduler_before_final_state_and_is_idempotent(self):
        runner = Scheduler()
        task = tasks.create("Test reminder", at="20m", runner=runner)
        finished = tasks.finish(task["id"], "completed", runner)
        self.assertEqual(runner.commands[-1][1], "disable")
        self.assertEqual(finished["status"], "completed")
        count = len(runner.commands)
        tasks.finish(task["id"], "completed", runner)
        self.assertEqual(len(runner.commands), count)
        self.assertEqual(tasks.reminder(task["id"]), "")

    def test_postpone_unknown_result_does_not_create_new_job(self):
        runner = Scheduler()
        task = tasks.create("Test reminder", at="20m", runner=runner)
        failing = Mock(json=Mock(side_effect=OperationError("request timed out")))
        with self.assertRaises(OperationError):
            tasks.postpone(task["id"], "30m", failing)
        self.assertEqual(failing.json.call_count, 1)

    def test_postpone_confirmed_missing_job_enables_replacement_after_metadata(self):
        runner = Scheduler()
        task = tasks.create("Test reminder", at="20m", runner=runner)
        original = runner.json
        def respond(name, args):
            if args[1] == "edit":
                raise OperationError("job not found")
            return original(name, args)
        runner.json = respond
        result = tasks.postpone(task["id"], "30m", runner)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(result["schedule"]["value"], "30m")
        self.assertEqual(runner.commands[-1][1], "enable")

    def test_scheduler_cannot_fire_before_active_metadata_exists(self):
        runner = Scheduler()
        original = runner.json
        observed = []
        def respond(name, args):
            if args[1] == "add":
                self.assertIn("--disabled", args)
                identifier = json.loads(args[args.index("--command-argv") + 1])[-1]
                observed.append(tasks.reminder(identifier))
            if args[1] == "enable":
                observed.append(tasks.list_tasks("all")[0]["status"])
            return original(name, args)
        runner.json = respond
        tasks.create("Test reminder", at="1s", runner=runner)
        self.assertEqual(observed, ["", "active"])

    def test_assignee_and_unconfigured_creator_cannot_grant_authority(self):
        runner = Scheduler()
        with self.assertRaises(OperationError):
            tasks.create("Test reminder", at="20m", created_by="Someone else", runner=runner)
        self.assertEqual(runner.commands, [])

    def test_corrupt_store_is_preserved(self):
        path = settings.home() / "private/tasks.json"
        path.write_text("invalid JSON")
        with self.assertRaises(ValueError):
            tasks.list_tasks()
        self.assertEqual(path.read_text(), "invalid JSON")

    def test_reconcile_never_recreates_missing_or_ambiguous_declarations(self):
        runner = Scheduler()
        task = tasks.create("Test reminder", at="20m", runner=runner)
        with tasks.store() as data:
            data["tasks"][task["id"]]["status"] = "uncertain"
        runner.jobs = []
        before = sum(args[1] == "add" for args in runner.commands)
        with self.assertRaises(OperationError):
            tasks.reconcile(task["id"], runner)
        self.assertEqual(sum(args[1] == "add" for args in runner.commands), before)
        self.assertEqual(tasks.show(task["id"])["status"], "uncertain")

    def test_reconcile_attaches_exact_existing_job_without_adding(self):
        runner = Scheduler()
        task = tasks.create("Test reminder", at="20m", runner=runner)
        with tasks.store() as data:
            data["tasks"][task["id"]]["status"] = "uncertain"
        result = tasks.reconcile(task["id"], runner)
        self.assertEqual(result["status"], "active")
        self.assertEqual(sum(args[1] == "add" for args in runner.commands), 1)
