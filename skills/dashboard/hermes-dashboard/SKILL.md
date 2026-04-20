---
name: hermes-dashboard
description: Read and interact with a running Hermes dashboard. Query today's activity summary, browse the content vault (drafts, media, prospects), check the approval queue, and record approval decisions. Requires a deployed Hermes dashboard with the standard API surface exposed. Configure via HERMES_DASHBOARD_URL.
version: 1.0.0
author: SpecCon / Hermes Agent
license: MIT
prerequisites:
  env_vars: [HERMES_DASHBOARD_URL]
  optional_env_vars: [HERMES_DASHBOARD_TOKEN]
metadata:
  hermes:
    tags: [dashboard, approvals, content-vault, activity, visibility]
---

# Hermes Dashboard

Query and interact with a running Hermes dashboard via its REST API.

The dashboard is a **read mirror of the agent's own activity** plus an **approval inbox** where humans review content before it ships. Every value in the dashboard originates from Hermes — the agent reads back its own work, surfaces it to humans, and then acts on their decisions.

## Setup

Set `HERMES_DASHBOARD_URL` in `~/.hermes/.env`:

```
HERMES_DASHBOARD_URL=http://claw.tail239156.ts.net:3100
HERMES_DASHBOARD_TOKEN=optional-bearer-token
```

If the dashboard has auth enabled, also set `HERMES_DASHBOARD_TOKEN` to a valid session token or API key.

## API Surface

All endpoints return JSON. Base URL comes from `$HERMES_DASHBOARD_URL`.

| Method | Path | What it returns |
|--------|------|----------------|
| `GET` | `/api/today` | Today's activity: sessions, cron runs, produced drafts, sent items |
| `GET` | `/api/approvals` | Pending approval queue: list of drafts awaiting review |
| `POST` | `/api/approvals` | Record a decision: approve, reject, or request rewrite |
| `GET` | `/api/vault/drafts` | All drafts with status, channel, and excerpt |
| `GET` | `/api/vault/media` | All media files (images, videos, audio) |
| `GET` | `/api/activity` | Session history and message feed (supports `?q=` FTS search) |
| `GET` | `/api/pipeline` | Pipeline companies and stages from Supabase |

## Quick Reference (curl)

### Check today's summary

```bash
curl -s "$HERMES_DASHBOARD_URL/api/today" \
  ${HERMES_DASHBOARD_TOKEN:+-H "Authorization: Bearer $HERMES_DASHBOARD_TOKEN"} \
  | python3 -m json.tool
```

### List pending approvals

```bash
curl -s "$HERMES_DASHBOARD_URL/api/approvals" \
  ${HERMES_DASHBOARD_TOKEN:+-H "Authorization: Bearer $HERMES_DASHBOARD_TOKEN"}
```

### Approve a draft

```bash
curl -s -X POST "$HERMES_DASHBOARD_URL/api/approvals" \
  ${HERMES_DASHBOARD_TOKEN:+-H "Authorization: Bearer $HERMES_DASHBOARD_TOKEN"} \
  -H "Content-Type: application/json" \
  -d '{"slug": "2026-04-20-email-agincare-first-touch", "decision": "approved", "reviewer": "andrew", "note": ""}'
```

### Request a rewrite

```bash
curl -s -X POST "$HERMES_DASHBOARD_URL/api/approvals" \
  -H "Content-Type: application/json" \
  -d '{"slug": "2026-04-20-email-agincare-first-touch", "decision": "rewrite", "reviewer": "andrew", "note": "Shorten to 80 words, signal is too vague"}'
```

### Browse the vault

```bash
# All drafts
curl -s "$HERMES_DASHBOARD_URL/api/vault/drafts" | python3 -c "
import json, sys
drafts = json.load(sys.stdin)
for d in drafts[:10]:
    print(f\"{d['status']:20} {d['channel']:12} {d['displayTitle']}\")
"

# All media
curl -s "$HERMES_DASHBOARD_URL/api/vault/media"
```

### Search activity

```bash
curl -s "$HERMES_DASHBOARD_URL/api/activity?q=Agincare"
```

## Python Client

For programmatic use, the included `scripts/dashboard_client.py` wraps the API:

```bash
source ~/.hermes/hermes-agent/venv/bin/activate
python3 ~/.hermes/hermes-agent/skills/dashboard/hermes-dashboard/scripts/dashboard_client.py today
python3 ~/.hermes/hermes-agent/skills/dashboard/hermes-dashboard/scripts/dashboard_client.py approvals
python3 ~/.hermes/hermes-agent/skills/dashboard/hermes-dashboard/scripts/dashboard_client.py approve 2026-04-20-email-agincare-first-touch
python3 ~/.hermes/hermes-agent/skills/dashboard/hermes-dashboard/scripts/dashboard_client.py reject 2026-04-20-email-agincare-first-touch "Signal too weak"
```

## When to Use This Skill

Load this skill when:

- Theo asks "what did you work on today?" or "what's pending?" — use `today` to give a precise answer
- You've produced drafts and want to check if any have been reviewed — use `approvals`
- You need to self-approve a Tier 1 piece after self-check passes — use `approve`
- You want to summarise your pipeline health — combine `today` + `pipeline`
- You're about to send and want to verify the item is APPROVED in the dashboard — use `approvals` and filter by slug

Do NOT call the dashboard API for every message. Load this skill purposefully when dashboard state is relevant to the current task.

## Response Shapes

### `GET /api/today`
```json
{
  "date": "Monday, 20 April 2026",
  "blurb": "Andrew worked for 3h 14m today. 3 drafts produced. 6 items await review.",
  "sessions": { "totalMinutes": 194, "sessionCount": 4, "toolCalls": 87 },
  "cronRuns": [
    { "jobId": "3edb756bfb01", "jobName": "morning-draft-queue", "runAt": "2026-04-20T09:02:20Z", "status": "ok" }
  ],
  "pendingDrafts": [
    { "slug": "2026-04-20-email-agincare-ft", "channel": "email", "displayTitle": "Agincare", "status": "PENDING_APPROVAL" }
  ],
  "sentToday": []
}
```

### `GET /api/approvals`
```json
[
  {
    "slug": "2026-04-20-email-agincare-ft",
    "displayTitle": "Agincare",
    "channel": "email",
    "signalTier": "S1",
    "subject": "23 open care roles in Bristol",
    "excerpt": "I noticed Agincare posted 23 care assistant roles across Bristol...",
    "status": "PENDING_APPROVAL"
  }
]
```

### `POST /api/approvals` request
```json
{
  "slug": "2026-04-20-email-agincare-ft",
  "decision": "approved",
  "reviewer": "andrew",
  "note": ""
}
```

### `POST /api/approvals` response
```json
{ "ok": true, "id": "uuid", "slug": "...", "decision": "approved" }
```
