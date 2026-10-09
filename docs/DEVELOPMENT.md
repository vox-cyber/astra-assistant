# Development and publishing

## Structure

- astra_app: stdlib Python CLI, settings, private core-tool bootstrap, isolated runtime, integrations, tasks, OAuth, notes/persona, optional workers and loopback dashboard.
- astra_app/web: local HTML/CSS/JavaScript; no CDN, bundler or UI npm dependency.
- plugins/astra-reply-resilience: ES-module OpenClaw plugin and standalone audio worker.
- config/settings.example.json: blank account template.
- docs: installation, use, coverage, integrations, privacy and recovery.
- examples/oauth-site: optional generic public website, no credentials/project IDs.
- tests: synthetic state/security/lifecycle/process fixtures. Never run live sends/consent as unit tests.
- scripts: release allowlist/scanner, optional native schema and UI smoke checks.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.mjs
python3 scripts/build_release.py --check
```

Native schema check uses an isolated temporary HOME/config and dry-run only:

```sh
python3 scripts/verify_schema.py
```

It requires OpenClaw 2026.9.1 and uses the built-in/pinned channel schema. It does not install over, restart, read credentials from or send through an existing gateway. Review any schema changes before upgrading the pin.

Browser checks (optional development dependency):

```sh
npm install --no-save --package-lock=false playwright
npx playwright install chromium
node scripts/ui_smoke.mjs
```

The smoke check starts an isolated test dashboard with a mock operation dispatcher. It exercises desktop/mobile navigation, settings, task UI, errors, private-client upload and safe rendering without native account/model calls. node_modules is excluded from the release.

You can use an existing Chromium/Chrome executable instead of downloading a Playwright browser: set `ASTRA_BROWSER=/path/to/chrome` before the smoke command. It opens a fresh temporary profile, never an existing account profile.

Package check:

```sh
python3 -m pip wheel . --no-deps --wheel-dir /tmp/astra-wheel
```

Setuptools >=68 is the build dependency; the application has no runtime Python dependencies. Wheel data includes plugin/guides. Check both source and installed CLI paths when changing resource locations or scheduler argv.

The core bootstrap is deliberately local: it runs `npm install --prefix ASTRA_HOME/tools --save-exact openclaw@2026.9.1 omniroute@3.8.51`. Never change it to `npm install -g` because a user may already have another OpenClaw installation.

## Source-only release

```sh
python3 scripts/build_release.py --check
python3 scripts/build_release.py
```

Outputs dist/astra-assistant-v0.1.0.zip and its SHA-256 file. The builder packages only known source/docs/test/template files, refuses symlinks and common sensitive artifact names/types, checks common secret patterns and nonblank example credentials, and excludes build/cache/node/runtime directories. Optional `--deny-file /outside/path.txt` checks deployment-specific private identifiers without embedding that list into the project or printing matched values. Keep the deny file outside the checkout.

Scanners cannot prove all personal prose absent; inspect intended release contents. Never release ASTRA_HOME/profile/backups, screenshots with account data, model keys, OAuth clients, contact lists or existing conversation/style stores.

## Upload to your GitHub repository

From a reviewed clean source checkout, use your own repository URL:

```sh
git init
git add README.md LICENSE .gitignore pyproject.toml launch.py start.sh astra_app config plugins docs examples tests scripts .github
git status
git diff --cached
git commit -m "Initial Astra Assistant release"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

These are instructions for the project owner; the assistant building this source bundle does not automatically create/push a repository. Do not stage dist, a venv, runtime configuration, caches, private backups or account exports. GitHub Actions runs Python/Node checks and a release scan. Add release ZIPs as release assets if desired, not private backups.

## Changes requiring particular care

Canonical requester authority, exact same-run cron proof, private storage corruption, automation-ID race handling, attempt-before-send persistence, suppression cutoffs, scheduler uncertainty and media containment are enforced boundaries. Test externally observable behavior, not copies of the implementation. Preserve user work and use the isolated profile for all native operations.

MIT applies to this source. OpenClaw, OmniRoute, gog, wacli, browsers, device tools and other dependencies retain their respective licenses; no dependency code/binaries are vendored.
