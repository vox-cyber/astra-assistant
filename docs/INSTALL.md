# Install and first launch

## Host and devices

Astra 0.1 targets a Linux host (Ubuntu/Debian or similar) with Python 3.10+ and a desktop browser. The dashboard and pure Python modules are portable, but reminders use Linux file locks, services use systemd user units, and speaker playback uses PulseAudio/PipeWire-compatible pactl. Android and Windows can be clients for notes and device access; native Windows/macOS assistant-host parity is not claimed.

Use Node.js 24.16+ in the 24.x line. OpenClaw 2026.9.1 also accepts specific recent 22.x/25.x releases, but 24.x is the straightforward supported choice. This release checks the exact OpenClaw 2026.9.1 version because its plugin hooks and schemas are version-sensitive.

## 1. Launch the setup dashboard

Open a terminal in the extracted project folder:

```sh
python3 --version
python3 launch.py
```

The browser opens automatically. If it does not, copy the full local link printed in the terminal. Keep that link private; its fragment is a local dashboard access token. Keep the terminal running. Ctrl+C stops the dashboard, not a separately installed assistant gateway.

No pip install is necessary. Optional installed CLI:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/astra
```

The installed package includes the plugin and guides. Keep its virtual environment if you install services/reminders using it.

## 2. Install the private core tools

Install Node 24.x using your preferred Node version manager or the official https://nodejs.org downloads. Confirm `node --version` and `npm --version`. Astra does not install Node itself because changing a system runtime requires your operating-system permissions.

```sh
python3 launch.py bootstrap
python3 launch.py router start
```

This installs pinned OpenClaw 2026.9.1 and OmniRoute 3.8.51 under `ASTRA_HOME/tools`, never with `npm -g`. The router uses its own data directory under `ASTRA_HOME/private/omniroute` and port 20129. It does not modify another OpenClaw profile or the existing OmniRoute installation.

Open http://127.0.0.1:20129, connect your own provider, and use its dashboard to select/enable the intended model. If OmniRoute requires an API key, create your own local router key and paste it into Astra's password field. No provider credential is included with this project.

OmniRoute's own bind/auth settings are separate from Astra's loopback dashboard. Configure them according to the current OmniRoute documentation: https://github.com/diegosouzapw/OmniRoute.

Default model: `omniroute/kg/kilo-auto/free`. Model availability, free-tier quotas and tool support depend on your provider. The optional fallback field starts empty. Add only models you have actually checked for the tasks you intend to run.

## 3. Save your details

In Guided setup:

- Display name: appears in the public fixed away reply.
- WhatsApp number: your full international number, starting with `+`.
- Timezone: IANA name such as `UTC`, `Europe/London`, or `America/New_York`.
- Delegates: optional canonical international numbers. They gain private device/account task access for explicit assistant requests; ordinary contact admission alone does not.
- Model/API fields: your router details. Blank API-key submission keeps an existing saved key.
- Away replies, owner voice playback and request-first public chat: optional, initially off.

Save, check the router catalog, then explicitly test one reply. The completion test sends only a small generic test prompt; it does not send a WhatsApp/Instagram message.

## 4. Apply and start the isolated runtime

Click Apply setup. This installs the pinned WhatsApp channel and Astra plugin under OpenClaw's separate `astra-community` profile, generates a private workspace, dry-runs the config patch, then applies it in one validated write. It does not import an existing default-profile account or session.

Click Install gateway service, then Start and Check health. From the terminal, the equivalents are:

```sh
python3 launch.py apply
python3 launch.py gateway install
python3 launch.py gateway start
python3 launch.py health
```

Profile gateway: loopback port 18791. Dashboard: loopback port 8765. Private router: loopback port 20129. These are separate processes.

After changing settings, save, apply and restart. Applying/restarting an existing running Astra profile requires all sessions to be idle; it preserves session history and queued work.

## 5. Add optional integrations

See INTEGRATIONS.md for:

- WhatsApp phone linking and optional wacli private history.
- Google gog CLI and your own Desktop OAuth client.
- Chrome/Chromium Instagram login and away watcher.
- ADB/scrcpy phone permissions.
- Speaker playback dependencies.
- Obsidian, Syncthing and Tailscale on Linux/Android/Windows.

Debian/Ubuntu optional system tools can be installed through your package manager:

```sh
sudo apt install adb scrcpy ffmpeg pulseaudio-utils
```

Install Chrome/Chromium using the official browser or your distribution's package instructions. Install gog and wacli using their official releases; see the links in the integration guide. Astra does not collect sudo passwords, Google/Instagram passwords or 2FA codes.

### What setup does and does not automate

The GitHub version automates the local dashboard, private settings, pinned core Node tools, isolated OpenClaw profile/plugin installation, config validation, gateway profile, task/reminder state, optional service templates and local workspace scaffolding. It does **not** automatically create or approve accounts, bypass OAuth/2FA, scan WhatsApp/Instagram QR codes, install Node/Chrome/ADB/sudo packages, choose a model provider, publish Google consent, pair Android/Tailscale/Syncthing devices, or claim that an account/API is ready without a real check. Those steps intentionally require you to approve the account's own login/consent screens.

## Persistent operation

The native gateway installer creates a profile-specific user service. Additional templates:

For a new OmniRoute installation, its official CLI can manage router autostart:

```sh
omniroute autostart status
omniroute autostart enable
```

Inspect an existing router service before changing it; Astra does not replace its provider settings or manage its credentials. The router must be available for cloud-model tasks after a reboot.

```sh
python3 launch.py services-install
systemctl --user enable --now astra-community-dashboard.service
systemctl --user enable --now astra-community-voice.service
```

Start voice only if you enabled owner voice playback and have local speakers. Optional history/recovery services are described in TROUBLESHOOTING.md. User services normally start with your login. If you intentionally want services after logout, configure systemd user lingering through `loginctl enable-linger "$USER"` with your OS's required authorization.

To open a service-hosted dashboard, run `python3 launch.py open`. For a custom port, add `--port 8766` (or the port you selected). Do not post its private link/token in issues. A future launcher tray is not included.
