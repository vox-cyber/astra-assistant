# Everyday use

## Dashboard

Overview shows installed software and saved configuration. “Installed” is not proof of a linked account. Guided setup saves identity/model settings and applies the runtime. Connections starts explicit login flows and bounded checks. Tasks creates and manages durable reminders. Ask Astra submits a real request to your persistent owner session. Local tools manages notes, samples, calendar files, service templates and private backups. Help reads bundled guides locally.

Operations run one at a time. The result panel distinguishes completion, failure and uncertainty. Closing the browser does not necessarily cancel an operation already executing; inspect status before resubmitting it.

## Owner self-chat

After linking WhatsApp, open Message yourself and write a specific request, such as:

- “Astra, list my Downloads files and suggest a tidy-up plan.”
- “Astra, create a reminder to stretch in 20 minutes.”
- “Astra, search my Google Drive for the project outline.”
- “Astra, you up?” is a local presence response, with no model needed.

Normal replies use OpenClaw's normal reply stream. Do not use a second message-send operation to deliver the same task answer. FIFO follow-up queueing preserves order; conflicting PC/account work should remain serialized. Check actual results, not just a successful CLI exit or scheduler tick.

Explicit configured delegate requests with Astra/nemo are eligible for private tasks in the delegate's own conversation. Delegate display names, assignee labels and quoted messages never authorize access.

## Professional away behavior

Enable in settings, apply, and restart. Ordinary new direct senders—including unsaved contacts—receive only the fixed Astra-identified notice once per 24 hours. No private context, tool or model is used. Groups and reactions are disabled.

Every detected human owner-sent WhatsApp message to any chat restarts the pause (15 minutes by default) on both WhatsApp and Instagram away replies. Observed owner online/typing/recording suppresses them too. Astra's generated messages are excluded. Opening WhatsApp is observable only when the linked client exposes owner presence; opening/using Instagram is not separately monitored. Suppressed messages are not replayed later.

STOP, unsubscribe and human handover persist. A sender can explicitly request “start Astra”/“resume Astra” to reopen admission. Owner requests and explicit delegate task requests remain available during the away quiet period, unless the entire platform is paused.

Optional request-first contact chat runs only while away is off and public chat is enabled. It is isolated general conversation with no PC tools, private files, owner memory or Google accounts. Per-peer FIFO/history and a two-completion global ceiling bound it.

### Time-limited replies

With professional away mode already enabled/applied/restarted, click “Limit enabled replies to 5 hours” or run `python3 launch.py away-for --hours 5` (up to 24 hours). The expiry is stored privately and checked at admission, final send and scheduled browser writes, so a delayed cleanup job cannot extend it. The model-free cleanup disables the matching Instagram watcher after expiry; stale windows cannot stop a newer window. Owner and explicit delegate tasks remain available. Set a fresh timer explicitly for a later window; no automatic renewal.

## CLI

Run these from the source folder. After a package install, `astra` is equivalent to `python3 launch.py`.

```sh
python3 launch.py status
python3 launch.py health
python3 launch.py model-check
python3 launch.py model-check --completion
python3 launch.py ask "Summarize the README in my current project."
python3 launch.py gateway start
python3 launch.py gateway restart
python3 launch.py gateway stop
```

Native runtime commands must include `--profile astra-community`:

```sh
openclaw --profile astra-community dashboard
openclaw --profile astra-community sessions --help
openclaw --profile astra-community cron list --all --json
```

Use supported session/history commands to inspect partially completed actions. Do not delete the session database to resolve model errors.

## Tasks and reminders

```sh
python3 launch.py task create "Take a short break" --at 20m
python3 launch.py task create "Daily review" --cron "0 18 * * *"
python3 launch.py task create "Check progress" --every 1h --assignee "Project team"
python3 launch.py task list --status all
python3 launch.py task show task-ID
python3 launch.py task postpone task-ID --at 30m
python3 launch.py task complete task-ID
python3 launch.py task cancel task-ID
python3 launch.py task reconcile task-ID
```

Replace task-ID with the returned `task-` ID. Unique prefixes are accepted. Metadata and scheduler jobs persist. Reminder delivery is always fixed to the configured owner number. Repeating reminders continue until completed/cancelled. The gateway and WhatsApp link must be available at delivery time.

Creation persists intent before scheduling, adds jobs disabled until active metadata exists, and reconciles a lost response by declaration key. An uncertain task is not automatically recreated. Inspect task and native jobs; use Reconcile existing scheduler job or `task reconcile` to attach/enable exactly one proved existing declaration. Missing/ambiguous declarations stay uncertain and no new job is added. The public UI does not implement general task editing, due/overdue filters or automatic daily summaries.

## Voice clips

Owner voice playback is optional. Enable in settings, apply/restart, install/start the voice unit. Eligible clips are only the canonical owner's default-account main self-chat, staged in this profile's inbound media store. Playback uses laptop speakers at 90%, without a model, then restores the previous port/volume/mute. Duplicate IDs are not replayed. The queue holds at most ten queued/playing clips; missing speakers/decoder/service produce an unconfirmed result.

## Notes, local calendar and style

```sh
python3 launch.py notes-init
python3 launch.py calendar-export --title "Planning session" --start "2030-01-01T09:00:00+00:00" --end "2030-01-01T10:00:00+00:00"
python3 launch.py persona collect --before "YOUR_PRE_ASTRA_CUTOFF_DATE"
python3 launch.py persona status
```

Choose a real cutoff BEFORE your own Astra deployment. Collection is read-only and requires separately authenticated/synced wacli history. Evidence is bounded to at most 1,000 scanned messages, eight qualifying direct chats and 24 samples per chat. Ask Astra in the private owner session to analyze it using the owner-voice skill. Validate profiles before applying them. Cloud analysis can transmit samples to your selected provider. Style observations never grant send authority or permission to impersonate you.

Local `.ics` export is a standalone file, not bidirectional Google Calendar synchronization. Notes are ordinary local Markdown; sync only the notes vault across devices.
