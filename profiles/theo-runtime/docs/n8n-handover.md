# n8n Integration — Handover Doc

**Purpose:** Connect the existing n8n instance to the Hermes/Polymarket/Trading stack and build the workflow layer.

**Date:** 2026-04-16

---

## 1. Current Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| **n8n** | Docker container (same host) | Workflow orchestration — webhook triggers, scheduling, multi-step pipelines |
| **Hermes** | This container (current) | AI reasoning layer — drafting, analysis, decision-making |
| **Polymarket Intel** | `~/polymarket-intel/` | Copy-intelligence engine — smart wallet tracking, consensus signals, paper trading |
| **MCP Server** | `~/polymarket-intel/mcp-server/polymarket_server.py` | FastMCP server exposing Polymarket data as agent tools |
| **OpenClaw** | Remote — `claw-host` (100.110.199.16) | WhatsApp gateway, multi-user session routing |
| **Firecrawl** | MCP server (local) | Web scraping, content extraction, brand audit |
| **SQLite DB** | `~/polymarket-intel/polymarket_intel.db` | Trade history, wallet scores, P&L tracking |

---

## 2. Network & Connectivity

### What n8n needs to reach (from its container):

| Service | Access Path | Notes |
|---------|-------------|-------|
| **Hermes** | `http://<hermes-container-ip>:<port>/webhook` or Docker network alias | n8n triggers Hermes for drafting/analysis tasks |
| **Polymarket APIs** | External — `https://gamma-api.polymarket.com`, `https://data-api.polymarket.com` | Public, no auth needed |
| **Polymarket MCP Server** | `http://<hermes-container-ip>:<mcp-port>` | FastMCP server running on this container |
| **Firecrawl MCP** | `http://<firecrawl-container-ip>:<port>` | For scraping tenders, news, competitor intel |
| **OpenClaw (claw-host)** | `100.110.199.16` | WhatsApp message routing via SSH/REST |
| **SQLite DB** | Volume mount or shared path `~/polymarket-intel/polymarket_intel.db` | Read/write access from n8n container |

### What the server manager needs to set up:

1. **Docker network:** Ensure n8n container and Hermes container are on the same Docker network so they can resolve each other by service name
2. **Volume mounts:** Share the `~/polymarket-intel/` directory (especially `polymarket_intel.db`) with n8n if n8n needs direct DB access
3. **Firewall rules:** n8n needs outbound HTTPS to Polymarket APIs
4. **DNS aliases:** If using Docker Compose, set service names so n8n can call `http://hermes:<port>` and `http://firecrawl:<port>` directly

---

## 3. Workflows to Build

### Priority 1 — Hermes Webhook Bridge

**Trigger:** Webhook (n8n receives request)
**Action:** Call Hermes API to run a scoped task (drafting, analysis, summarization)
**Response:** Return result to caller

```
[Webhook] → [HTTP Request: Hermes] → [Format Response] → [Webhook Response]
```

**Use cases:**
- "Draft a summary for tender X"
- "Analyze this Polymarket signal"
- "Generate a compliance checklist"

### Priority 2 — Polymarket Signal Monitor

**Trigger:** Cron (every 30 min) or manual
**Action:** Run Polymarket intel scan → detect consensus → alert

```
[Cron Trigger] → [HTTP: Polymarket Intel CLI / MCP] → [Filter: consensus 3+ wallets] → [IF signal found] → [Alert: Discord/Telegram/WhatsApp]
```

**Data sources:**
- `https://gamma-api.polymarket.com/markets` — market discovery
- `https://data-api.polymarket.com/trades` — live trades
- Local `polymarket_intel.db` — wallet scores

### Priority 3 — Tender Intake Pipeline

**Trigger:** Cron (every 4 hours)
**Action:** Scrape → deduplicate → extract PDFs → store → notify

```
[Cron Trigger] → [Firecrawl: scrape EasyTenders] → [Deduplicate vs known] → [Firecrawl: extract PDF text] → [Store in R2/local] → [Write discovery.md] → [Alert]
```

**Integrates with:** Firecrawl MCP for scraping, R2/S3 for storage

### Priority 4 — Self-Healing Feedback Loop

**Trigger:** After any trade resolves
**Action:** Update wallet scores, log outcome, detect drift

```
[Webhook: trade resolved] → [SQLite: update P&L] → [Recalculate wallet scores] → [IF strategy drift detected] → [Alert: review needed]
```

---

## 4. API Endpoints & Secrets

### Polymarket (public, no auth):
- **Gamma API:** `https://gamma-api.polymarket.com/markets`
- **Data API:** `https://data-api.polymarket.com/trades`
- **CLOB API:** `https://clob.polymarket.com/`

### Internal services:
- **Hermes API:** `<to be confirmed — need container IP and port>`
- **Firecrawl MCP:** `<to be confirmed — need container IP and port>`
- **Polymarket MCP Server:** `~/polymarket-intel/mcp-server/polymarket_server.py` (tools: `getmarkets`, `getevents`, `gettrades`)

### Secrets to manage (if using Infisical or env vars):
- Polymarket CLOB API keys (if placing live orders later)
- OpenClaw API credentials (for WhatsApp routing)
- Firecrawl API key (if using cloud Firecrawl)
- Discord/Telegram webhook URLs (for alerts)

---

## 5. MCP Server — Polymarket

The Polymarket MCP server is already built and registered in Hermes config (`~/.hermes/config.yaml`). For n8n to use it:

**Option A:** n8n calls Hermes which uses MCP tools internally (simplest)
**Option B:** n8n calls the MCP server directly via HTTP (needs the MCP HTTP transport enabled)

**Tools exposed:**
| Tool | Description |
|------|-------------|
| `getmarkets` | Fetch/filter markets — params: `active`, `closed`, `slug`, `tag` |
| `getevents` | Group related markets into events |
| `gettrades` | Recent trades — filter by `proxyWallet` |

**Repo:** `https://github.com/TheophilusChinomona/polymarket-intel`

---

## 6. Questions for the Server Manager

1. What port is n8n running on? (default `5678`)
2. What's the Docker network name connecting the containers?
3. Is there a shared volume path for `~/polymarket-intel/`?
4. What container runs the Firecrawl MCP server?
5. What container/port runs Hermes API?
6. Are there existing Docker Compose files we should add the n8n service to?
7. Is Infisical already deployed for secrets, or should we use env vars for now?

---

## 7. Architecture Diagram

```
                    ┌─────────────────┐
                    │   WhatsApp/      │
                    │   Discord Users  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   OpenClaw      │
                    │   (claw-host)   │
                    │  100.110.199.16 │
                    └────────┬────────┘
                             │ webhooks
                    ┌────────▼────────┐
                    │     n8n         │  ← Workflows live here
                    │  (this host)    │
                    └───┬─────┬───┬───┘
                        │     │   │
            ┌───────────┘     │   └────────────┐
            ▼                 ▼                ▼
    ┌───────────────┐ ┌──────────────┐ ┌───────────────┐
    │   Hermes      │ │ Firecrawl    │ │ Polymarket    │
    │   (AI layer)  │ │ MCP Server   │ │ Intel Engine  │
    │               │ │              │ │ + MCP Server  │
    └───────────────┘ └──────────────┘ └───────┬───────┘
                                               │
                                        ┌──────▼──────┐
                                        │  SQLite DB  │
                                        │  trades.db  │
                                        └─────────────┘
```
