"""Explicit, bounded read-only style collection. Private evidence never ships."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
from . import settings
from .commands import OperationError, Runner


def root():
    return settings.home() / "workspace/persona"


def collect(before, runner=None):
    if not settings.load()["owner_phone"]:
        raise OperationError("Configure your owner identity before collecting style evidence")
    try:
        cutoff = datetime.fromisoformat(before.replace("Z", "+00:00"))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        marker = settings.home() / "private/first-setup.json"
        boundary = datetime.fromisoformat(json.loads(marker.read_text())["first_setup_at"]) if marker.exists() else datetime.now(timezone.utc)
        if cutoff >= boundary:
            raise ValueError("Cutoff must precede first setup")
    except (ValueError, AttributeError):
        raise OperationError("Choose a cutoff date before Astra started sending messages")
    data = (runner or Runner()).json("wacli", ["--store", str(settings.home() / "private/wacli"), "--read-only", "--json", "messages", "list",
                                            "--from-me", "--before", before, "--limit", "1000"])
    if data.get("success") is False:
        raise OperationError("The read-only history query failed")
    rows = data.get("data", {}).get("messages", [])
    grouped = defaultdict(list)
    owner = settings.load()["owner_phone"].lstrip("+")
    for row in rows:
        jid, text = row.get("ChatJID", ""), row.get("Text", "")
        if not row.get("FromMe") or not text or jid.split("@")[0] == owner or not jid.endswith(("@lid", "@s.whatsapp.net")):
            continue
        if any(row.get(k) for k in ("IsForwarded", "Revoked", "DeletedForMe", "ReactionToID")):
            continue
        if re.search(r"astra|\b(?:otp|password|verification code|api.?key|access.?token)\b", text, re.I):
            continue
        key = hashlib.sha256(jid.encode()).hexdigest()[:16]
        grouped[key].append({"id": row.get("MsgID"), "timestamp": row.get("Timestamp"),
                             "text": re.sub(r"\b\d{5,}\b", "[number]", re.sub(r"https?://\S+", "[link]", text))[:480]})
    conversations = []
    for key, messages in sorted(grouped.items(), key=lambda item: -len(item[1]))[:8]:
        if len(messages) >= 6:
            count = min(24, len(messages))
            sample = [messages[round(i * (len(messages) - 1) / (count - 1))] for i in range(count)]
            conversations.append({"contactKey": key, "messages": sample})
    coverage = {"collected_at": datetime.now(timezone.utc).isoformat(), "cutoff": before,
                "scanned": len(rows), "conversations": len(conversations),
                "samples": sum(len(c["messages"]) for c in conversations)}
    settings.write_private(root() / "history-sample.json", {"coverage": coverage, "conversations": conversations})
    return coverage


def status():
    path = root() / "history-sample.json"
    if not path.exists():
        return {"samples": 0, "profile_ready": False, "message": "No private style sample collected"}
    sample = json.loads(path.read_text())
    errors = []
    profile_path = root() / "contacts.json"
    style_path = root() / "STYLE.md"
    profiles = json.loads(profile_path.read_text()).get("contacts", []) if profile_path.exists() else []
    sources = {c["contactKey"]: c["messages"] for c in sample["conversations"]}
    seen = set()
    for profile in profiles:
        key = profile.get("contactKey")
        if key not in sources or key in seen:
            errors.append("Unknown or duplicate contact evidence")
            continue
        seen.add(key)
        ids = {m["id"] for m in sources[key]}
        if not profile.get("evidenceMessageIds") or not set(profile["evidenceMessageIds"]) <= ids:
            errors.append("Profile cites unsupported evidence")
        if profile.get("sampleCount") != len(sources[key]) or profile.get("confidence") not in ("low", "medium", "high"):
            errors.append("Invalid sample count or confidence")
    ready = bool(sources) and seen == set(sources) and not errors and style_path.exists() and bool(style_path.read_text().strip())
    return {**sample["coverage"], "profile_ready": bool(ready), "issues": errors,
            "message": "Create/edit a profile in the private owner session, then validate it. No messages are sent by collection."}
