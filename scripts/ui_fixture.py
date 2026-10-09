"""Isolated synthetic dashboard for Playwright; no account or native tool calls."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from astra_app import settings, tasks
from astra_app.server import Dashboard, Jobs
from astra_app.commands import OperationError


def dispatch(action, params):
    if action == "settings.save":
        return settings.save(params)
    if action == "tasks.create":
        with tasks.store() as data:
            value = {"id": "task-abcdef123456", "title": params["title"], "status": "active", "assignee": "me",
                     "schedule": {"kind": "at", "value": params.get("at", "20m"), "timezone": "UTC"}}
            data["tasks"][value["id"]] = value
            return value
    if action == "google.import":
        return {"message": "Synthetic client accepted; no OAuth or account operations performed."}
    if action == "ask":
        return {"text": "Synthetic answer: <img src=x onerror=alert('unsafe')>"}
    if action == "model.test":
        raise OperationError("Synthetic provider unavailable")
    return {"message": "Synthetic action completed; no native tools invoked."}


if __name__ == "__main__":
    server = Dashboard(("127.0.0.1", 0), "synthetic-ui-session", Jobs(dispatch))
    print(json.dumps({"port": server.server_port}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
