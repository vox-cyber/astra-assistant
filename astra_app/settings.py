"""Private local settings; never store account configuration in the checkout."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import sys

PROJECT = Path(__file__).resolve().parents[1]
PROFILE = "astra-community"
ROUTER_PORT = 20129


def resources():
    if (PROJECT / "plugins/astra-reply-resilience/openclaw.plugin.json").is_file():
        return PROJECT
    return Path(sys.prefix) / "share/astra-assistant"
DEFAULTS = {
    "owner_name": "", "owner_phone": "", "owner_lid": "", "delegates": [],
    "primary_model": "omniroute/kg/kilo-auto/free",
    "fallback_models": [], "provider_url": "http://127.0.0.1:20129/v1",
    "provider_api_key": "", "google_email": "", "google_client_file": "",
    "instagram_username": "", "instagram_job_id": "", "timezone": "UTC",
    "away_enabled": False, "away_quiet_minutes": 15, "voice_autoplay": False, "public_chat_enabled": False,
    "runtime_configured": False,
}
PHONE = re.compile(r"\+[1-9]\d{6,14}\Z")


def home():
    value = Path(os.environ.get("ASTRA_HOME", str(Path.home() / ".local/share/astra"))).expanduser().resolve()
    if (PROJECT / "pyproject.toml").exists() and value.is_relative_to(PROJECT):
        raise ValueError("ASTRA_HOME must be outside the source project to protect private account data")
    return value


def settings_path():
    return home() / "private/settings.json"


def write_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, temporary = tempfile.mkstemp(prefix=".astra-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load():
    path = settings_path()
    if not path.exists():
        return deepcopy(DEFAULTS)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Settings must be a JSON object")
    return {**deepcopy(DEFAULTS), **value}


def validate(value):
    for field in ("owner_name", "owner_phone", "owner_lid", "google_email", "google_client_file",
                  "instagram_username", "instagram_job_id", "timezone", "provider_api_key", "primary_model", "provider_url"):
        if not isinstance(value.get(field), str) or len(value[field]) > 2048 or "\x00" in value[field]:
            raise ValueError(f"Invalid {field.replace('_', ' ')}")
    if len(value["owner_name"]) > 80 or any(c in value["owner_name"] for c in "\n\r"):
        raise ValueError("Use a short, single-line display name")
    if value["owner_phone"] and not PHONE.fullmatch(value["owner_phone"]):
        raise ValueError("Enter your full international phone number, starting with +")
    if value["owner_lid"] and not re.fullmatch(r"\d{7,20}@lid", value["owner_lid"]):
        raise ValueError("Leave the optional linked identity blank unless you know its exact value")
    delegates = value.get("delegates")
    if not isinstance(delegates, list) or len(delegates) > 10 or any(not isinstance(x, str) or not PHONE.fullmatch(x) for x in delegates):
        raise ValueError("Delegates must be a list of international phone numbers")
    for field in ("away_enabled", "voice_autoplay", "public_chat_enabled", "runtime_configured"):
        if type(value.get(field)) is not bool:
            raise ValueError(f"{field} must be true or false")
    if type(value.get("away_quiet_minutes")) is not int or not 1 <= value["away_quiet_minutes"] <= 120:
        raise ValueError("Activity pause must be between 1 and 120 minutes")
    if not isinstance(value.get("fallback_models"), list) or len(value["fallback_models"]) > 5:
        raise ValueError("Use a list of at most five fallback models")
    models = [value["primary_model"], *value["fallback_models"]]
    if any(not isinstance(x, str) or not re.fullmatch(r"omniroute/[\w./:-]+", x) for x in models):
        raise ValueError("Use fully qualified omniroute model names")
    url = urlsplit(value["provider_url"])
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Enter an HTTP(S) API base URL without embedded credentials")
    if value["google_email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value["google_email"]):
        raise ValueError("Enter a valid Google account email")
    if value["instagram_username"] and not re.fullmatch(r"@?[\w.]{1,64}", value["instagram_username"]):
        raise ValueError("Enter an Instagram username, not a password")
    try:
        ZoneInfo(value["timezone"])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Choose a valid IANA timezone, such as UTC or Europe/London")
    return value


def save(changes):
    unknown = set(changes) - set(DEFAULTS)
    if unknown or "runtime_configured" in changes or "instagram_job_id" in changes:
        raise ValueError("Unsupported settings field")
    value = load()
    # An empty password field means keep the locally saved key. Clearing is explicit.
    if changes.get("provider_api_key") == "":
        changes = {k: v for k, v in changes.items() if k != "provider_api_key"}
    value.update(changes)
    validate(value)
    write_private(settings_path(), value)
    return public(value)


def public(value=None):
    value = deepcopy(value if value is not None else load())
    value["provider_key_configured"] = bool(value.pop("provider_api_key", ""))
    return value


def owner_ids(value=None):
    value = value or load()
    return [x for x in (value["owner_phone"], value["owner_lid"]) if x]


def away_text(value=None):
    value = value or load()
    name = value["owner_name"] or "the account owner"
    return (f"Hello, I'm Astra, {name}'s AI assistant. {name} is currently occupied and unable to respond immediately. "
            "Please leave your message for them to review when they are available. Thank you for your understanding.")
