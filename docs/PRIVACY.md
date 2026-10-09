# Privacy, authority and local data

## What is published

Source code, empty settings, generic docs, synthetic test fixtures, service-generation code and a generic optional website. No real user's accounts, contact list, OTP/pairing codes, browser profiles, keyrings, conversations, model keys or private style evidence are distributed.

Tests contain clearly synthetic reserved/example identities and non-working test strings so that authority boundaries can be verified; these are not account credentials or published real contacts.

## What is stored after setup

- ASTRA_HOME (default ~/.local/share/astra): private settings, dashboard/gateway tokens, pinned core tools, private OmniRoute data, Google client/keyring/password, task metadata, guard reservations/pauses, voice queue, local calendar and isolated wacli history.
- ASTRA_HOME/workspace: owner instructions, memory, checkpoints, private style samples/profiles and Instagram watcher receipts.
- ~/.openclaw-astra-community: profile config, credentials, sessions, inbound media and dedicated browser data.
- ~/Documents/Astra Notes: ordinary notes you choose to sync.
- ~/.local/share/astra-backups: separately created PRIVATE backups containing account data.

Private JSON writes are atomic with 0600 files and private parent directories. This protects against other ordinary OS users, not the same local account or an administrator. The Google file keyring's local password is stored for unattended use; do not treat it as inaccessible to the host account. Backups need your own secure/encrypted storage.

ASTRA_HOME must stay outside the source checkout. The public release builder uses an allowlist and checks for sensitive artifacts, but no automated scanner can prove that arbitrary prose contains no personal information. Review files before publishing your changes.

## Data leaving the computer

Cloud model prompts and content you select for an assistant task go through OmniRoute to the selected provider. Google/WhatsApp/Instagram operations talk to their platforms. A private owner-requested style analysis can transmit sampled messages to the model provider. Obsidian/Syncthing/Tailscale have their own device/network behavior and policies. The local dashboard has no analytics or external assets.

Fixed WhatsApp away replies do not call a model or load private context. Optional public contact chat sends only that peer's bounded conversation/general prompt to the chosen model with no PC/account tools or private owner memory. It explicitly identifies Astra as an AI assistant.

## Authority

Owner/delegate canonical identities are configured by the user. Host-provided sender identity is required for WhatsApp tool access. Names, wildcard admission, a senderIsOwner flag without the configured sender, assignee text, quoted messages, websites and documents do not grant authority.

Instagram cron authority requires the exact configured job/session/main-agent/trigger/no-sender host proof associated with the same run. Another run cannot borrow it. The lane allows only specified policy/state files, the dedicated profile and exact guard RPC commands.

The native dashboard token controls the local assistant. HTTP API calls require bearer authentication, correct local Host and acceptable Origin. The server binds only to loopback, disallows framing, does not expose arbitrary-shell HTTP routes, and does not return provider secrets. Keep its URL/token and browser session private. For other-device access, use an intentional authenticated tunnel/SSH arrangement rather than changing the HTTP bind to a public interface; turnkey remote dashboard access is not implemented.

## Messaging controls and limits

Fixed away text, opt-outs, persistent restrictions, pre-send attempt reservations, duplicate suppression, sender/day/hour ceilings and owner-activity gating reduce unwanted sends. Attempts, including unconfirmed delivery, count before transport. Limits are configurable implementation defaults, not Meta-approved safe rates.

Restriction/rate-limit/verification signals persist across restarts. Resume requires an explicit admin operation after genuine review; service restarts never automatically clear pauses. Never solve challenges through another client, proxy rotation or fingerprint spoofing.

These are personal linked-device/browser integrations. They are unofficial and do not guarantee that an account will avoid restrictions. An official API deployment requires its own genuine eligibility, permissions, consent, webhooks and platform review.

## Deletion and revocation

Stop services first. Revoke linked devices in WhatsApp, Google app access in your Google account, and Instagram sessions where appropriate. Follow TROUBLESHOOTING.md for uninstall. Delete the profile/private directories only when you intentionally want to remove credentials/history and have preserved anything needed. Deleting a Syncthing-shared note can delete it on other devices; use a separate backup.

When reporting issues, share only version and redacted metadata. Do not upload your private settings/backup, full logs, QR, account identifiers, message bodies, OAuth JSON or token URL.
