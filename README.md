# ✦ Astra Assistant

**Your assistant. Your accounts.** A guided local dashboard and operator CLI for a Linux-hosted personal assistant, powered by OpenClaw and your own OmniRoute providers.

Connect WhatsApp self-chat, Google apps, an Instagram browser profile, and Android screen control. Keep durable reminders, a local notes vault, keyword memory, and bounded owner-style evidence. Setup is explicit: installed software, account authorization, model responses, and actual delivery are different states.

## Start here

1. Download/extract this project or clone your copy, then open a terminal in its folder.
2. With **Python 3.10+** and Node.js **24.16+ in the 24.x line**, run:

   ```sh
   python3 launch.py
   ```

3. Use **Guided setup** in the browser. The dashboard itself requires no Python dependencies or pip install.
4. Click **Install private core tools**, or run `python3 launch.py bootstrap`. This installs **OpenClaw 2026.9.1** and **OmniRoute 3.8.51** under Astra's private data directory, not globally.
5. Start the private router, connect your own provider in OmniRoute, save your identity, check a model response, apply setup, install/start the gateway, and connect the apps you want.

The browser link contains a private local access token. Keep that link private. The dashboard binds only to `127.0.0.1`, not your LAN.

## Included

| Area | What the project provides |
| --- | --- |
| Beginner interface | Guided setup, connection actions, tasks, owner requests, tools, local help and explicit operation results |
| Assistant runtime | Separate `astra-community` OpenClaw profile, persistent owner session, FIFO follow-up queues, OmniRoute-only models, local keyword memory |
| WhatsApp | Linking UI, canonical owner/delegate authority, contact isolation, opt-outs, fixed professional away text, activity pause, durable timed expiry, no reactions/groups/bulk sends |
| Instagram | Dedicated login profile, exact-job scoped watcher, read-only first tick, bounded candidates, durable reservations, activity-aware away gating |
| Google | Private Desktop OAuth client import and gog wrapper for nine Workspace services |
| Tasks | Stable IDs, locked state, owner-only command-scheduled reminders, completion/cancellation/postponement and uncertain-create reconciliation |
| Audio | Owner self-chat clip queue, local speaker playback at 90%, duplicate suppression and audio-setting restoration |
| Local tools | ADB/scrcpy selection, private history reads, bounded style samples, notes initialization, standalone `.ics` export |
| Operations | User-service templates, model-free guarded recovery, pause-aware history sync, offline private backups and recovery instructions |
| Cross-device | Tailscale, Syncthing and Obsidian setup guide; optional generic OAuth website template |

See [Feature coverage](docs/FEATURES.md) for implementation boundaries and what needs your own accounts/hardware. Public tests use synthetic fixtures; they do not authenticate accounts or send real test messages.

## Privacy by default

- This repository contains **source code and blank configuration**, not an existing user's credentials, phone numbers, profiles, conversations, style samples or history.
- Runtime data lives outside the checkout: `~/.local/share/astra` and `~/.openclaw-astra-community`.
- A separate profile and gateway port (`18791`) isolate this setup from an existing default OpenClaw installation.
- API keys and OAuth files are never returned by the dashboard's settings endpoint.
- The core bootstrap does not install Node itself or perform account consent; those actions stay under your control.
- Cloud model requests send prompts and any task-selected content to your selected provider. This is not an entirely offline AI system.
- Personal WhatsApp linking and Instagram browser automation are unofficial transports. The guard's local ceilings are not platform-approved limits or a ban-prevention guarantee.

Read [Privacy and authority](docs/PRIVACY.md) before connecting accounts.

## Operator examples

Run from the checkout, or replace `python3 launch.py` with `astra` after installing the Python package:

```sh
python3 launch.py status
python3 launch.py health
python3 launch.py ask "List my Downloads files and suggest an organization plan."
python3 launch.py task create "Take a short break" --at 20m
python3 launch.py task list
python3 launch.py google status
python3 launch.py phone status
```

## Guides

- [Install and first launch](docs/INSTALL.md)
- [Everyday usage and CLI](docs/USAGE.md)
- [Account and three-device connections](docs/INTEGRATIONS.md)
- [Feature coverage](docs/FEATURES.md)
- [Privacy, authority and data](docs/PRIVACY.md)
- [Troubleshooting, backups and uninstall](docs/TROUBLESHOOTING.md)
- [Development, tests and GitHub publishing](docs/DEVELOPMENT.md)

## Development

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.mjs
python3 scripts/build_release.py --check
```

Optional browser checks use Playwright; see the development guide. Build a source-only release with `python3 scripts/build_release.py`. MIT licensed; dependencies retain their own licenses.
