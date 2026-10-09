# Feature coverage

This is the public, configurable implementation. Prior private deployment evidence is not transferred as a claim that new users' accounts are connected. Tests use synthetic identities/data and mocks. Account-, model- and hardware-dependent behavior must be verified on the user's machine.

| Feature | Included implementation | What you still provide/verify |
| --- | --- | --- |
| Setup UI | Loopback authentication, guided setup, safe DOM text rendering, fixed operations, bounded job queue | Python/browser and your own settings |
| Core bootstrap | Pinned OpenClaw 2026.9.1 and OmniRoute 3.8.51 installed under ASTRA_HOME/tools, or compatible existing binaries wrapped with isolated paths; separate OmniRoute data/port | Node.js itself, provider account/model sign-in and optional OS tools |
| Persistent assistant | Isolated OpenClaw main session and profile; no session reset on apply | Pinned OpenClaw, working gateway and model/tool support |
| OmniRoute routing | Configurable API URL/key, qualified primary/fallbacks, catalog/completion checks | Provider account, quotas and task-appropriate models |
| FIFO/progress/recovery | Follow-up queue settings, style agreement, bounded empty-final recovery without tool replay | Runtime behavior with your model; read actual task results |
| Owner/delegate PC tasks | Canonical host identity guard; own persistent session; owner task UI | OS permissions and intended delegate choices |
| Reminders/tasks | Locked/atomic state, declaration reconciliation, fixed owner delivery, lifecycle methods | Gateway/WhatsApp online at delivery |
| WhatsApp away | Fixed text, unsaved direct senders, 24-hour per-peer reservation, opt-outs, no reactions/groups | Own linked personal account; unofficial transport |
| Owner activity | Existing authenticated socket observation; any manual outgoing chat/presence; automation IDs; reconnect | Runtime context/socket availability; no guaranteed app-foreground detection |
| Timed reply mode | Durable up-to-24-hour deadline in admission/send/browser gates; model-free matching-window cleanup; owner tasks preserved | Already-enabled away mode and a fresh explicit timer; no automatic renewal |
| Public contact chat | Optional request-first zero-tool isolated completion lane; bounded per-peer FIFO | Explicit enable, away off, working model |
| Instagram | Dedicated login; dynamic exact-job watcher; initial read-only state; scoped tools; reservations | Own account/browser, direction/time/recipient evidence, current layout |
| Google apps | Desktop OAuth import/login, isolated named-client keyring; Gmail/Drive/Calendar/Contacts/Tasks/Docs/Sheets/Slides/Forms wrapper | Own cloud project, APIs/scopes/consent and data-specific checks |
| Phone control | ADB status, explicit serial, scrcpy launch, generated skill | Connected authorized Android device and OS/device permissions |
| History | Isolated wacli store, read-only wrapper, pause-aware sync service | Own separately linked history client |
| Style learning | Bounded pre-Astra sample, hashed contact keys, evidence validation and skill | Owner-requested analysis/profile edits; no preloaded personal samples |
| Voice notes | Owner-only staged clips, local SQLite queue, speaker selection, 90%, restoration/dedupe | Local audio hardware and service/dependencies |
| Memory | Local keyword-only OpenClaw configuration and private workspace | Meaningful owner-approved notes, current runtime indexing |
| Notes/calendar | Non-destructive notes init and standalone timezone-aware .ics | Chosen notes/calendar apps; no automatic Google calendar sync |
| Three-device setup | Detailed Obsidian/Syncthing/Tailscale instructions | Installation, account sign-in, device pairing and connectivity |
| Services/recovery | User units; model-free authenticated/unpaused/idle recovery; sync stops on unavailable authorization | Enable chosen units; manually resolve verification/restrictions |
| Private backups | Offline source/account archive outside repository, private modes | Stop writers, secure/encrypt destination, manual trusted restore |
| OAuth public website | Generic static homepage/privacy template and Firebase instructions | Own disclosures/project/domain; publishing/brand review not automatic |
| Release | Source-only allowlist, sensitive artifact checks, Python/Node tests, CI | Review your own changes before publishing |

## Explicit boundaries

- Linux is the supported assistant host; Android/Windows client setup is documented. No turnkey universal OS installer/tray/auto-updater.
- No preconnected accounts, transferable OAuth consent, personal model credentials or shared private history.
- No official WhatsApp Business/Instagram API migration or Meta approval provisioned.
- No Instagram-user activity observer, guaranteed WhatsApp app-open detection, or Android foreground daemon.
- No proof of actual new-user DM delivery from unit tests or read-only readiness.
- Guarded OpenClaw hooks do not govern every external program or arbitrary browser/shell action on a user's machine.
- No automated task daily digest, generic task editor, due/overdue search or bidirectional calendar synchronization.
- Profile/text policies assist behavior; host identity/tool/storage guards enforce the explicit implemented boundaries. Do not describe prompts alone as security isolation.

Use the feature-specific guide and inspect actual outcomes rather than treating installation or scheduler success as semantic completion.
