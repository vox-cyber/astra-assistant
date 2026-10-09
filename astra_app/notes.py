"""A local notes vault and standalone iCalendar export, not Google sync."""
from datetime import datetime, timezone
from pathlib import Path
import uuid
from . import settings
from .commands import OperationError


def vault():
    return Path.home() / "Documents/Astra Notes"


def initialize():
    target = vault()
    target.mkdir(parents=True, exist_ok=True)
    for name in ("Inbox", "Projects", "Daily Notes", "Attachments"):
        (target / name).mkdir(exist_ok=True)
    for name, content in {"Home.md": "# Astra Notes\n\nYour notes, projects and daily journal.\n",
                          ".stignore": ".obsidian/workspace*\n.obsidian/cache\n"}.items():
        path = target / name
        try:
            with path.open("x") as stream:
                stream.write(content)
        except FileExistsError:
            pass
    return {"message": "Notes vault is ready. Pair only this folder in Syncthing; keep account data elsewhere.", "path": str(target)}


def event(title, start, end):
    def utc(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise OperationError("Include a timezone offset in calendar dates")
        return parsed.astimezone(timezone.utc)
    first, last = utc(start), utc(end)
    if last <= first:
        raise OperationError("The event must end after it starts")
    title = title.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;").replace("\r", "")
    identifier = uuid.uuid4().hex
    body = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Astra//Local calendar//EN",
                        "BEGIN:VEVENT", "UID:" + identifier + "@astra.local",
                        "DTSTAMP:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                        "DTSTART:" + first.strftime("%Y%m%dT%H%M%SZ"), "DTEND:" + last.strftime("%Y%m%dT%H%M%SZ"),
                        "SUMMARY:" + title, "END:VEVENT", "END:VCALENDAR", ""])
    path = settings.home() / "private/calendar" / (identifier + ".ics")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(body)
    path.chmod(0o600)
    return {"path": str(path), "message": "Local .ics created. Import it into your chosen calendar; this does not synchronize Google Calendar."}
