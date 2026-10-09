"""Astra's operator interface. Run without arguments to open guided setup."""
import argparse
import json
import os
from pathlib import Path
import sys
from . import settings, tasks, runtime, integrations, google, persona, notes
from .commands import OperationError, Runner, redact


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Open local guided setup")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-browser", action="store_true")
    opening = sub.add_parser("open", help="Open an already-running dashboard using its private local link")
    opening.add_argument("--port", type=int, default=8765)
    sub.add_parser("status", help="Inspect installed tools and private setup metadata")
    sub.add_parser("health", help="Check the isolated gateway and guard")
    configure = sub.add_parser("configure", help="Save settings from a private JSON file or stdin")
    configure.add_argument("--file", type=Path)
    sub.add_parser("apply", help="Install plugin and validate/apply isolated runtime settings")
    sub.add_parser("bootstrap", help="Install pinned OpenClaw and OmniRoute outside the repository")
    router = sub.add_parser("router")
    router.add_argument("action", choices=("start", "stop", "restart"))
    gateway = sub.add_parser("gateway")
    gateway.add_argument("action", choices=("install", "start", "stop", "restart"))
    ask = sub.add_parser("ask", help="Request a task in the persistent owner session")
    ask.add_argument("prompt")
    model = sub.add_parser("model-check")
    model.add_argument("--completion", action="store_true", help="Make one explicit test model request")
    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="action", required=True)
    create = task_sub.add_parser("create")
    create.add_argument("title")
    timing = create.add_mutually_exclusive_group(required=True)
    timing.add_argument("--at")
    timing.add_argument("--every")
    timing.add_argument("--cron", dest="expression")
    create.add_argument("--assignee", default="me")
    create.add_argument("--created-by", default="owner")
    listing = task_sub.add_parser("list")
    listing.add_argument("--status", choices=("active", "completed", "cancelled", "uncertain", "all"), default="active")
    for name in ("show", "complete", "cancel", "postpone", "reconcile"):
        command = task_sub.add_parser(name)
        command.add_argument("id")
        if name == "postpone":
            command.add_argument("--at", required=True)
    reminder = sub.add_parser("remind", help=argparse.SUPPRESS)
    reminder.add_argument("id")
    gs = sub.add_parser("google")
    gsub = gs.add_subparsers(dest="action", required=True)
    for name in ("status", "login"):
        gsub.add_parser(name)
    client = gsub.add_parser("import-client")
    client.add_argument("file", type=Path)
    run = gsub.add_parser("run")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    ig = sub.add_parser("instagram")
    ig.add_argument("action", choices=("login", "watch-create", "watch-enable", "watch-disable"))
    phone = sub.add_parser("phone")
    phone.add_argument("action", choices=("status", "screen"))
    phone.add_argument("--serial")
    ps = sub.add_parser("persona")
    ps.add_argument("action", choices=("status", "collect"))
    ps.add_argument("--before")
    history = sub.add_parser("history", help="Read-only local WhatsApp history")
    history.add_argument("arguments", nargs=argparse.REMAINDER)
    guard = sub.add_parser("guard")
    guard.add_argument("action", choices=("status", "pause", "resume"))
    guard.add_argument("--platform", choices=("whatsapp", "instagram"))
    guard.add_argument("--reviewed", action="store_true", help="Explicit operator review before resuming a paused platform")
    sub.add_parser("notes-init")
    event = sub.add_parser("calendar-export")
    for name in ("title", "start", "end"):
        event.add_argument("--" + name, required=True)
    sub.add_parser("services-install")
    sub.add_parser("backup", help="Create a PRIVATE account/settings backup outside the project")
    window = sub.add_parser("away-for", help="Set a durable expiry for already-enabled professional replies")
    window.add_argument("--hours", type=float, default=5)
    expiry = sub.add_parser("away-expire", help="Internal matching-window cleanup")
    expiry.add_argument("id")
    worker = sub.add_parser("worker", help="Run an explicitly enabled model-free background worker")
    worker.add_argument("kind", choices=("recovery", "history"))
    return root


def execute(args):
    if args.command in (None, "serve"):
        from .server import serve
        return serve(getattr(args, "port", 8765), not getattr(args, "no_browser", False))
    if args.command == "status":
        return integrations.inspect()
    if args.command == "open":
        import webbrowser
        path = settings.home() / "private/dashboard-token.json"
        if not path.exists() or not 1024 <= args.port <= 65535:
            raise OperationError("Start the dashboard first and choose its valid port")
        secret = json.loads(path.read_text())["token"]
        webbrowser.open(f"http://127.0.0.1:{args.port}/#session={secret}")
        return {"message": "Private dashboard link opened in your browser."}
    if args.command == "health":
        return integrations.health()
    if args.command == "configure":
        return settings.save(json.loads(args.file.read_text() if args.file else sys.stdin.read()))
    if args.command == "apply":
        return runtime.apply()
    if args.command == "bootstrap":
        return runtime.bootstrap()
    if args.command == "router":
        return runtime.router(args.action)
    if args.command == "gateway":
        return runtime.gateway(args.action)
    if args.command == "ask":
        return runtime.ask(args.prompt)
    if args.command == "model-check":
        return runtime.model_check(args.completion)
    if args.command == "task":
        if args.action == "create":
            return tasks.create(args.title, at=args.at, every=args.every, expression=args.expression,
                                assignee=args.assignee, created_by=args.created_by)
        if args.action == "list":
            return tasks.list_tasks(args.status)
        if args.action == "show":
            return tasks.show(args.id)
        if args.action == "postpone":
            return tasks.postpone(args.id, args.at)
        if args.action == "reconcile":
            return tasks.reconcile(args.id)
        return tasks.finish(args.id, "completed" if args.action == "complete" else "cancelled")
    if args.command == "remind":
        print(tasks.reminder(args.id))
        return None
    if args.command == "google":
        if args.action == "run":
            print(google.gog(args.arguments))
            return None
        if args.action == "import-client":
            return google.import_client(json.loads(args.file.read_text()))
        return google.login() if args.action == "login" else google.status()
    if args.command == "instagram":
        return integrations.instagram_login() if args.action == "login" else runtime.instagram_watch(args.action == "watch-enable")
    if args.command == "phone":
        return integrations.phone_screen(args.serial) if args.action == "screen" else integrations.phone_status()
    if args.command == "persona":
        return persona.collect(args.before) if args.action == "collect" else persona.status()
    if args.command == "history":
        return integrations.history(args.arguments)
    if args.command == "guard":
        if args.action != "status" and not args.platform:
            raise OperationError("Choose --platform whatsapp or instagram")
        if args.action == "resume" and not args.reviewed:
            raise OperationError("Review account standing and the pause cause first, then pass --reviewed")
        return runtime.call("astra.messagingGuard." + args.action, None if args.action == "status" else
                            {"platform": args.platform, "reviewed": args.reviewed})
    if args.command == "notes-init":
        return notes.initialize()
    if args.command == "calendar-export":
        return notes.event(args.title, args.start, args.end)
    if args.command == "services-install":
        return integrations.install_services()
    if args.command == "backup":
        return integrations.backup()
    if args.command == "away-for":
        return runtime.away_window(args.hours)
    if args.command == "away-expire":
        return runtime.away_expire(args.id)
    if args.command == "worker":
        from . import workers
        return workers.recovery() if args.kind == "recovery" else workers.history()


def main(argv=None):
    os.umask(0o077)
    try:
        result = execute(parser().parse_args(argv))
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OperationError, ValueError, OSError) as exc:
        print("Astra: " + redact(str(exc)), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
