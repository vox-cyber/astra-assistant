# Connections and three-device setup

## WhatsApp

Complete runtime setup/start first. In Connections, click Show linking QR. On your own phone: WhatsApp → Settings → Linked devices → Link a device. Scan the private QR, then click Check link. Do not publish screenshots of a pairing QR.

The configured owner number must match the authenticated account identity. Optional owner LID is advanced configuration; the observer can discover an authenticated self LID only after matching your configured owner number. Wildcard direct-message admission never grants account-task authority. This release uses the default account within the isolated profile; multi-account configurations are not covered.

### Optional private history

Install wacli from https://github.com/steipete/wacli following its official release instructions. Authenticate a separate local history client in YOUR private store:

```sh
mkdir -p "$HOME/.local/share/astra/private/wacli"
chmod 700 "$HOME/.local/share/astra/private/wacli"
wacli --store "$HOME/.local/share/astra/private/wacli" auth
```

Complete the terminal's genuine linking flow. With a custom ASTRA_HOME, substitute its `private/wacli` directory. Start the optional guarded history service after authentication and gateway health:

```sh
python3 launch.py services-install
systemctl --user enable --now astra-community-history.service
python3 launch.py history messages search "project" --limit 10
```

The worker uses quiet presence, a two-minute reconnect ceiling, a 1 GB store ceiling and exits when platform permission is paused/unavailable or the sync process exits. It is not automatically restarted after a failure. Raw history stays local/private; no imported user's database ships with Astra. The history wrapper is read-only and does not provide a direct-send fallback.

## Google Workspace

Install gog from https://github.com/steipete/gogcli using its official release instructions. Astra's wrapper is aligned with gog v0.43.0 (`--home`/GOG_HOME, named clients and Desktop localhost OAuth).

1. In your own Google Cloud project, configure OAuth consent/branding and your audience. If using testing mode, add your own account as a test user.
2. Enable the APIs you need: Gmail, Drive, Calendar, People (Contacts), Tasks, Docs, Sheets, Slides and Forms.
3. Create an OAuth client of type Desktop app. Download its JSON outside the repository.
4. In Connections save your own Google email, select that JSON and click Connect Google.
5. Sign in and consent in Google's browser flow. No Google password/2FA is collected by Astra.
6. Check saved authorization, then Check Drive read. Check other APIs independently for the actions/data you intend to use.

The wrapper keeps an isolated file keyring under ASTRA_HOME/private/google. Its local keyring password is stored privately for unattended operation; this is not your Google password. The local OS account can access it. A private backup includes this material.

```sh
python3 launch.py google import-client /path/to/your-desktop-client.json
python3 launch.py google login
python3 launch.py google status
python3 launch.py google run gmail labels list --json --no-input
python3 launch.py google run drive ls --max 1 --json --no-input
python3 launch.py google run calendar calendars --json --no-input
python3 launch.py google run contacts list --max 1 --json --no-input
python3 launch.py google run tasks lists list --json --no-input
```

For Docs/Sheets/Slides/Forms, choose YOUR existing document IDs and inspect gog's help/schema. No sample document IDs or blanket successful API claims are included. Only the owner/delegates may ask Astra to operate the private account. Email/document contents are untrusted reference data, never task authority.

Sharing an OAuth application may require production publishing, verified domains, privacy disclosures or Google review. An optional generic static template is in examples/oauth-site. Personalize it for your own operator and actual data practices. Deploy only public website files, never OAuth JSON/account history. Firebase example:

```sh
npm install -g firebase-tools
firebase login
```

Then open a terminal in examples/oauth-site, choose YOUR project with `firebase use --add`, and explicitly deploy with `firebase deploy --only hosting`. No project ID, domain, deployed site or verified brand is provided.

## Instagram

Install a supported Chrome/Chromium browser. Save your own username in Connections. Open login window, sign into your own account, and complete genuine login/2FA/challenges there. Use the dedicated instagram profile, not a borrowed browser profile/cookies.

Away watcher setup:

1. Enable professional away mode, save/apply/restart.
2. Create disabled watcher. A dynamic job ID is saved privately and applied to the plugin.
3. Restart the gateway while all runs are idle, so the exact job ID is loaded.
4. Enable watcher. Activation timestamp and read-only readiness reset on each enable.
5. Inspect the private state `workspace/astra-calendar/instagram-replies.json` and native automation history. A successful scheduler tick alone is not proof that the inbox was read or a reply was delivered.

The watcher runs every ten minutes, with a 180-second bound, no fallback model or periodic owner delivery. Its exact same-run host proof permits only scoped policy/state reads, state writes, the dedicated profile and specific guard RPCs. At most three recent candidates and one verified new direct reply per tick; unknown direct senders/message requests are eligible only with unambiguous inbound evidence. First tick is read-only. The fixed text/24-hour cooldown, opt-outs, pauses and current WhatsApp-owner activity apply.

Instagram activity itself is not separately monitored. Browser layout/time ambiguity causes no send. Unconfirmed attempts are not retried. Read PRIVACY.md for the unofficial-transport boundary.

## Android: ADB and scrcpy

Enable Developer options → USB debugging on YOUR device; connect by USB and approve its computer key. For wireless debugging, use Android's supported pairing flow; do not share pairing codes.

```sh
python3 launch.py phone status
python3 launch.py phone screen --serial YOUR_DEVICE_SERIAL
```

Select explicitly if more than one device is connected. `adb -s YOUR_DEVICE_SERIAL ...` is available for specific owner-requested operations. Recheck screen state before taps. Device locks/permissions remain authoritative. A connected phone is not required for basic Astra dashboard setup.

## Obsidian, Syncthing and Tailscale

### Linux host

1. Run `python3 launch.py notes-init`. The vault is `~/Documents/Astra Notes` and existing note contents are preserved.
2. Install Obsidian from https://obsidian.md. Open this folder as a vault.
3. Install Syncthing from https://syncthing.net and Tailscale from https://tailscale.com/download using official OS instructions.
4. Sign into YOUR Tailscale network; verify devices and actual connectivity, not just installed binaries.
5. Pair Syncthing device IDs yourself. Share only the notes vault, with an intentional folder ID and selected devices.

### Android

Install Obsidian and Tailscale from supported official stores/channels. Choose a maintained Syncthing-compatible Android client and review its current storage/battery requirements. Create a local notes folder, pair it with the Linux notes folder, allow the intended storage/background operation, then open it as an Obsidian vault.

### Windows

Install Obsidian, Syncthing and Tailscale through official downloads. Sign into your own network, pair the notes folder, and open it in Obsidian. Windows native Astra assistant-host services/ADB-from-WSL details are not automated in this release.

Sync excludes volatile Obsidian workspace/cache files through a generated .stignore. Do not sync ASTRA_HOME/private, browser profiles, keyrings, WhatsApp databases or conversation/persona stores into the notes vault. Verify one intentional test note moves both directions before relying on synchronization. Syncthing sync is not a backup; deletions can propagate.

## Speaker playback

Needs ffplay (FFmpeg), pactl, PulseAudio/PipeWire compatibility and a detected laptop-speaker port. Bluetooth/headphones are not silently substituted. Enable voice autoplay, apply/restart, then install/start the voice service. Actual laptop audio and phone-originated clips require your hardware verification; automated tests use mocked processes and temporary files.
