---
name: from-hermes-agent
description: Migrate from upstream Hermes Agent (NousResearch) to Athena. Since Athena is a direct fork with identical internal paths, all data is 100% compatible — this is purely a repo switch + skin update. No data migration required.
version: 1.0.0
author: Athena (SpecCon)
license: MIT
metadata:
  hermes:
    tags: [Migration, Hermes, Athena, Upgrade, Fork]
    related_skills: [openclaw-migration]
---

# Upstream Hermes Agent → Athena Migration

Use this skill when a user is running upstream Hermes Agent (NousResearch/hermes-agent) and wants to switch to Athena.

## Key fact

Athena is a direct fork of Hermes Agent with **identical internal paths**:
- Runtime data lives at `~/.hermes/` — unchanged
- CLI command stays `hermes` — unchanged
- Config schema is identical — unchanged
- All env vars (`HERMES_*`) stay — unchanged

This means **zero data migration**. The switch is a repo + skin change only.

## Two migration paths

### Path A: Fresh install (recommended for clean setups)

The simplest path. Your `~/.hermes/` data is untouched — reinstalling only replaces the code.

```bash
# 1. Back up existing install (optional but recommended)
cp -r ~/.hermes/hermes-agent ~/.hermes/hermes-agent.bak.$(date +%Y%m%d)

# 2. Run the Athena install script
curl -fsSL https://raw.githubusercontent.com/TheophilusChinomona/hermes-agent/main/scripts/install.sh | bash

# 3. Apply Athena skin
hermes config set display.skin athena

# 4. Restart gateway if running
systemctl --user restart hermes-gateway.service   # Linux
# or: hermes gateway restart
```

### Path B: Git remote switch (for git-installed setups)

If you installed via `git clone`, switch the remote and pull.

```bash
cd ~/.hermes/hermes-agent

# 1. Add Athena as a remote
git remote add athena https://github.com/TheophilusChinomona/hermes-agent.git

# 2. Fetch and switch to Athena main
git fetch athena
git checkout -b athena-main athena/main

# 3. Rebuild the venv
source venv/bin/activate
uv pip install -e ".[all]"

# 4. Apply Athena skin
hermes config set display.skin athena

# 5. Restart gateway
systemctl --user restart hermes-gateway.service
```

## What Athena adds over upstream

| Area | What changed |
|---|---|
| Session DB | Errors surfaced instead of silently swallowed |
| Persona (SOUL.md) | Hardened loading across all gateway paths — no more drift |
| WhatsApp | Media delivery + formatting reliability |
| LanceDB | Moved to external module `hermes-memory-lancedb` |
| Supabase | Client dependency added |
| Default skin | Athena skin — silver/midnight-blue strategy theme |

## Default workflow

1. Ask whether the user installed via git clone or the install script.
2. Recommend Path A for install-script users, Path B for git users.
3. Walk through the chosen path step by step.
4. After switching, confirm the banner shows "Athena" by running `hermes --version` or starting a chat session.
5. If gateway was running, confirm it restarts cleanly by checking `cat ~/.hermes/gateway_state.json`.

## Verification

After migration, confirm:
- `hermes` opens with the Athena banner (silver/midnight-blue, "strategy engine ready")
- `cat ~/.hermes/gateway_state.json` shows platforms as previously connected
- Sessions, memories, and SOUL.md are intact in `~/.hermes/`
