"""Locked task metadata around OpenClaw's durable command scheduler."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
import sys
import uuid
try:
    import fcntl
except ImportError:
    fcntl = None
from . import settings
from .commands import OperationError, Runner


def stamp():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def store():
    if fcntl is None:
        raise OperationError("The reminder worker currently requires a Linux host")
    path = settings.home() / "private/tasks.json"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.with_suffix(".lock").open("a+") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text()) if path.exists() else {"version": 1, "tasks": {}}
        if data.get("version") != 1 or not isinstance(data.get("tasks"), dict):
            raise OperationError("The task store is invalid; preserve it and restore a private backup")
        try:
            yield data
            data["updated_at"] = stamp()
            settings.write_private(path, data)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def clean(text, limit=240):
    if not isinstance(text, str) or not text.strip() or len(text) > limit or "\x00" in text:
        raise OperationError("Enter a nonempty task title or schedule within its length limit")
    return " ".join(text.split())


def resolve(data, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r"task-[a-f0-9]{1,12}", identifier):
        raise OperationError("Choose a valid task ID")
    matches = [v for k, v in data["tasks"].items() if k.startswith(identifier)]
    if len(matches) != 1:
        raise OperationError("Task ID is missing or ambiguous")
    return matches[0]


def job_id(response):
    if isinstance(response, dict):
        for key in ("id", "jobId", "job_id"):
            if isinstance(response.get(key), str) and response[key]:
                return response[key]
        for value in response.values():
            found = job_id(value)
            if found:
                return found
    return None


def cron(runner, args):
    result = runner.json("openclaw", ["cron", *args, "--json"])
    if result.get("ok") is False:
        raise OperationError("Scheduler rejected the operation")
    return result


def declaration(task):
    return f"astra-task:{task['id']}:v{task['revision']}"


def all_jobs(runner):
    rows, offset = [], 0
    for _ in range(5):
        params = json.dumps({"includeDisabled": True, "limit": 200, "offset": offset})
        page = runner.json("openclaw", ["gateway", "call", "cron.list", "--params", params, "--json"])
        if not isinstance(page.get("jobs"), list):
            raise OperationError("Cannot establish complete scheduler state")
        rows.extend(page["jobs"])
        if not page.get("hasMore"):
            return rows
        following = page.get("nextOffset")
        if not isinstance(following, int) or following <= offset:
            break
        offset = following
    raise OperationError("Scheduler result is incomplete; inspect it in the native dashboard")


def create_job(runner, task):
    cfg = settings.load()
    timing = task["schedule"]
    args = ["add", "--name", f"Astra reminder {task['id']}", "--description", "Owner-only task reminder",
            "--declaration-key", declaration(task), "--command-argv",
            json.dumps([sys.executable, "-m", "astra_app", "remind", task["id"]]),
            "--command-cwd", str(settings.PROJECT),
            "--command-env", "ASTRA_HOME=" + str(settings.home()), "--timeout-seconds", "30",
            "--disabled",
            "--announce", "--channel", "whatsapp", "--account", "default", "--to", cfg["owner_phone"],
            "--" + timing["kind"], timing["value"], "--tz", timing["timezone"]]
    if timing["kind"] == "at":
        args.append("--delete-after-run")
    try:
        result = cron(runner, args)
        identifier = job_id(result)
        if not identifier:
            raise OperationError("Scheduler did not confirm a job ID")
        return identifier
    except OperationError as exc:
        # A create response can be lost after acceptance. Reconcile once; never
        # blindly add a second job with the same task declaration.
        try:
            jobs = all_jobs(runner)
            matches = [j for j in jobs if j.get("declarationKey") == declaration(task)]
            if len(matches) == 1:
                return matches[0]["id"]
        except OperationError:
            pass
        raise OperationError("Reminder creation is uncertain. Inspect this task and runtime jobs before retrying.") from exc


def create(title, *, at=None, every=None, expression=None, assignee="me", created_by="owner", runner=None):
    cfg = settings.load()
    if not cfg["owner_phone"]:
        raise OperationError("Set your WhatsApp number before creating owner-only reminders")
    allowed = [cfg["owner_phone"], *cfg["delegates"]]
    creator = cfg["owner_phone"] if created_by == "owner" else created_by
    if creator not in allowed:
        raise OperationError("Creator metadata must name the owner or a configured delegate")
    chosen = [(kind, value) for kind, value in (("at", at), ("every", every), ("cron", expression)) if value]
    if len(chosen) != 1:
        raise OperationError("Choose exactly one reminder time, interval or cron expression")
    kind, value = chosen[0]
    task = {"id": "task-" + uuid.uuid4().hex[:12], "title": clean(title), "status": "provisioning",
            "assignee": clean(assignee, 80), "created_by": creator, "created_at": stamp(), "revision": 1,
            "schedule": {"kind": kind, "value": clean(value, 200), "timezone": cfg["timezone"]},
            "job_id": None, "last_reminded_at": None}
    with store() as data:
        if len(data["tasks"]) >= 500:
            raise OperationError("The local task store is full; archive old tasks first")
        data["tasks"][task["id"]] = task
    try:
        task["job_id"] = create_job(runner or Runner(), task)
        task["status"] = "active"
    except OperationError:
        with store() as data:
            data["tasks"][task["id"]]["status"] = "uncertain"
        raise
    with store() as data:
        data["tasks"][task["id"]] = task
    try:
        cron(runner or Runner(), ["enable", task["job_id"]])
    except OperationError:
        with store() as data:
            data["tasks"][task["id"]]["status"] = "uncertain"
        raise OperationError("Reminder enabling is uncertain; inspect its scheduler job before retrying")
    return task


def list_tasks(status="active"):
    with store() as data:
        return [dict(t) for t in data["tasks"].values() if status == "all" or t["status"] == status]


def show(identifier):
    with store() as data:
        return dict(resolve(data, identifier))


def finish(identifier, state, runner=None):
    if state not in ("completed", "cancelled"):
        raise OperationError("Unsupported final task state")
    task = show(identifier)
    if task["status"] in ("completed", "cancelled"):
        return task
    if task["status"] != "active":
        raise OperationError("Resolve this task's uncertain scheduler state first")
    try:
        cron(runner or Runner(), ["disable", task["job_id"]])
    except OperationError as exc:
        missing = re.search(r"not found|unknown automation|does not exist", str(exc), re.I)
        if not (missing and task["schedule"]["kind"] == "at" and task["last_reminded_at"]):
            raise
    with store() as data:
        record = resolve(data, identifier)
        record.update(status=state, finished_at=stamp())
        return dict(record)


def postpone(identifier, at, runner=None):
    task = show(identifier)
    if task["status"] != "active":
        raise OperationError("Only an active reminder can be postponed")
    runner = runner or Runner()
    recreated = False
    args = ["edit", task["job_id"], "--at", clean(at, 200), "--delete-after-run"]
    try:
        cron(runner, args)
    except OperationError as exc:
        if not re.search(r"not found|unknown automation|does not exist", str(exc), re.I):
            with store() as data:
                resolve(data, identifier)["status"] = "uncertain"
            raise OperationError("Reminder postponement is uncertain; inspect its scheduler job before retrying") from exc
        task["revision"] += 1
        task["schedule"] = {**task["schedule"], "kind": "at", "value": at}
        try:
            task["job_id"] = create_job(runner, task)
            recreated = True
        except OperationError:
            with store() as data:
                resolve(data, identifier).update(status="uncertain", revision=task["revision"])
            raise
    with store() as data:
        record = resolve(data, identifier)
        record.update(job_id=task["job_id"], revision=task["revision"], last_reminded_at=None,
                      schedule={**task["schedule"], "kind": "at", "value": at})
        result = dict(record)
    if recreated:
        try:
            cron(runner, ["enable", task["job_id"]])
        except OperationError:
            with store() as data:
                resolve(data, identifier)["status"] = "uncertain"
            raise OperationError("Postponed reminder enabling is uncertain; inspect its scheduler job")
    return result


def reminder(identifier):
    with store() as data:
        task = resolve(data, identifier)
        if task["status"] != "active":
            return ""
        task["last_reminded_at"] = stamp()
        text = "Astra reminder: " + task["title"]
        if task["assignee"] != "me":
            text += "\nAssignee: " + task["assignee"]
        if task["schedule"]["kind"] != "at":
            text += "\nRepeats until completed or cancelled."
        return text


def reconcile(identifier, runner=None):
    """Attach/enable exactly one proved existing declaration; never add a job."""
    runner = runner or Runner()
    task = show(identifier)
    if task["status"] not in ("uncertain", "provisioning"):
        raise OperationError("Only an uncertain/provisioning task needs reconciliation")
    matches = [job for job in all_jobs(runner) if job.get("declarationKey") == declaration(task)]
    if len(matches) != 1:
        raise OperationError("No unique existing scheduler declaration is proved. No new job was created.")
    job = matches[0]
    with store() as data:
        record = resolve(data, identifier)
        record.update(job_id=job["id"], status="active")
    try:
        if job.get("enabled") is not True:
            cron(runner, ["enable", job["id"]])
    except OperationError:
        with store() as data:
            resolve(data, identifier)["status"] = "uncertain"
        raise
    return show(identifier)
