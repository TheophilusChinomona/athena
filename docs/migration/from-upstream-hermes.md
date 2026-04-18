# Migrating from upstream Hermes Agent to Athena

Athena is a direct fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) with identical internal paths. All your data lives at `~/.hermes/` and is 100% compatible — no data migration required. The switch is a repo change + skin update only.

## Path A: Fresh install (recommended)

Your `~/.hermes/` data is untouched — reinstalling only replaces the code.

```bash
# Optional: back up the existing install
cp -r ~/.hermes/hermes-agent ~/.hermes/hermes-agent.bak.$(date +%Y%m%d)

# Install Athena
curl -fsSL https://raw.githubusercontent.com/TheophilusChinomona/hermes-agent/main/scripts/install.sh | bash

# Apply Athena skin
hermes config set display.skin athena

# Restart gateway if running
systemctl --user restart hermes-gateway.service
```

## Path B: Git remote switch

If you installed via `git clone`:

```bash
cd ~/.hermes/hermes-agent

# Add Athena remote and switch branch
git remote add athena https://github.com/TheophilusChinomona/hermes-agent.git
git fetch athena
git checkout -b athena-main athena/main

# Rebuild dependencies
source venv/bin/activate
uv pip install -e ".[all]"

# Apply Athena skin + restart
hermes config set display.skin athena
systemctl --user restart hermes-gateway.service
```

## What stays the same

Everything. `~/.hermes/` path, `hermes` CLI binary, `HERMES_*` env vars, config schema, sessions, memories, SOUL.md, skills — all untouched.

## What Athena adds

| Area | Change |
|---|---|
| Session DB | Errors surfaced (no more silent swallowing) |
| Persona | SOUL.md loading hardened across all gateway paths |
| WhatsApp | Media delivery + formatting reliability |
| LanceDB | External module instead of bundled |
| Supabase | Client dependency included |

## Verify the switch

```bash
hermes          # Should show Athena banner (silver/midnight-blue)
cat ~/.hermes/gateway_state.json   # Platforms should show as before
```
