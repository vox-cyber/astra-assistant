# Troubleshooting, services, backups and uninstall

## Start with a specific state

`python3 launch.py status` reports installed tools and saved setup metadata. `health` checks the isolated guard, not every provider/API. Use model-check --completion for one model response. Account authorization, a successful read API and confirmed delivery are separate evidence.

### Dashboard won't open

- Python 3.10+ required. Run from the extracted source folder.
- Open the full link printed by launch.py; a bare localhost URL lacks its private token.
- Port 8765 already in use: stop the dashboard user service, or choose `serve --port 8766`.
- An old browser tab may have an old token; use the current private launch link.
- Do not expose the dashboard through a public bind or paste its link into support messages.

### Missing/incompatible OpenClaw

Install the exact documented 2026.9.1 version. New versions need hook/schema revalidation before changing this pin. Node 24.16+ within 24.x is recommended. Ensure executables are in PATH or set local ASTRA_OPENCLAW/ASTRA_GOG/etc. executable overrides.

### Apply/restart says busy or cannot prove idle

Wait for all tasks/queued runs/subagents to finish; inspect the native dashboard/sessions. Do not reset sessions or bypass the gate. If this is initial setup, apply is possible before a gateway exists; a configured profile requires idle evidence for changes. To recover a genuinely stopped profile, start its gateway before applying changes.

### Router/catalog works but model fails

Check provider sign-in, quota, selected model and API key in OmniRoute. Catalog presence alone does not prove a completion or tool support. A missing/filtered/timeout final answer is not proof of a network outage. Some task tools may already have run; inspect their outputs before retrying. Empty-final recovery never replays tools.

### WhatsApp not linked/replying

Start the gateway; use the private linking QR and Check link. Match your configured owner number to the authenticated account. Check persistent platform pauses and recipient opt-out/cooldown. Away mode fails closed when the owner observer is unavailable/active. Groups and reactions are intentionally disabled. Account verification belongs in the platform's own flow.

### Instagram watcher silent

Verify browser login and exact username. Create the disabled job, restart the gateway to load its ID, then enable. First tick is read-only. Inspect state/history for a real readiness outcome, not only cron status. Check pauses, owner quiet period, inbound timestamps/activation, recipient evidence and existing attempt receipts. Ambiguity means no send. No backlog replay or repeated browser retry cycles.

### Google access fails

Use your own Desktop OAuth JSON, email, enabled APIs and correct testing/production consent. Reconnect through the genuine browser. Saved auth is not proof every API works. Follow gog's current command help for specific document operations. Never include the client JSON, local keyring password or token in an issue.

### Reminder uncertain

Inspect the task's stable ID, status, declaration key/revision and native automation list. A lost create response may mean a job was accepted. Do not add another reminder blindly. Postponement recreates only a confirmed-missing job; uncertain operations stay uncertain. The gateway/link need to be available for owner delivery.

Use the UI's Reconcile existing scheduler job or `python3 launch.py task reconcile task-ID`. This attaches/enables only a unique already-existing declaration; it never creates a replacement for missing/ambiguous evidence.

### Voice not playing

Check ffplay/pactl, laptop-speaker port, service and staged inbound path. Enable voice autoplay, apply/restart. No speaker/headphone substitution or repeated duplicate playback is performed. Restarted/interrupted clips are recorded as interrupted rather than automatically replayed. Actual hardware needs your local check.

## Services

```sh
python3 launch.py services-install
systemctl --user status openclaw-gateway-astra-community.service
systemctl --user enable --now astra-community-dashboard.service
systemctl --user enable --now astra-community-voice.service
systemctl --user enable --now astra-community-recovery.service
systemctl --user enable --now astra-community-history.service
```

Enable only what you use. History needs its own wacli linking first. Recovery makes no model calls/sends: it acts only on a proved linked but disconnected account, working guard, unpaused platform and idle sessions. Unknown state/auth failure/verification is not recovery permission. History stops on pause/unavailable permission and has no automatic failure restart. Native linked-client reconnect behavior is separate from this worker.

Pause or explicitly resume after genuine account review:

```sh
python3 launch.py guard pause --platform whatsapp
python3 launch.py guard status
python3 launch.py guard resume --platform whatsapp --reviewed
```

Use instagram for that platform. A restart never clears persisted guard state. Preserve corrupt stores; do not overwrite them to claim health.

## Private backups and restoration

Public source ZIP and private runtime backup are different artifacts. Stop all account writers before backup: browser, history, voice/recovery workers and then the idle gateway. Do not copy a changing SQLite/browser store as a claimed consistent snapshot.

```sh
systemctl --user stop astra-community-history.service astra-community-recovery.service astra-community-voice.service
openclaw --profile astra-community browser --browser-profile instagram stop
python3 launch.py gateway stop
python3 launch.py backup
```

Backup refuses a listening Astra gateway and writes a 0600 archive under ~/.local/share/astra-backups. It includes private Astra data and the isolated OpenClaw profile, skips symlinks/devices/browser caches, and does not upload anything. The dashboard can remain running, but avoid settings changes while backing up. Stop OmniRoute separately and follow its own backup procedure if you also need provider credentials/settings; Astra's backup does not archive ~/.omniroute.

Restore only a trusted backup while writers are stopped. Inspect archive paths, extract into a temporary PRIVATE directory, preserve current data first, and copy the astra and openclaw-profile trees to your own intended ASTRA_HOME and ~/.openclaw-astra-community. Do not extract untrusted archives blindly. On a new machine, executable/venv paths and browser/device state can differ: fix your settings/service paths, start the profile, apply/restart safely, and reconnect accounts if required. Restoring a backup does not justify replaying uncertain sends/tasks.

## Uninstall

First stop/disable only this project's units:

```sh
systemctl --user disable --now astra-community-dashboard.service astra-community-history.service astra-community-recovery.service astra-community-voice.service
python3 launch.py gateway stop
openclaw --profile astra-community gateway uninstall
```

Remove the four generated astra-community unit files after inspecting them; reload the user daemon. If installed into a venv, uninstall astra-assistant there. You can keep notes/backups. Revoke account links/access in the platforms themselves. Remove ASTRA_HOME and the isolated profile only if you intend to delete its credentials/history. Do not remove a default OpenClaw profile or another user's configuration.
