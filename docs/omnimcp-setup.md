# OmniMCP Setup for Andrew

OmniMCP is the unified MCP gateway for the theochinomona.tech stack — one HTTPS endpoint, Infisical-scoped access, all services (Firecrawl, n8n, vault, CaptureIQ CRM).

**Endpoint:** `https://mcp.theochinomona.tech/mcp`

## Prerequisites

Andrew needs an Infisical machine identity. Do this once:

```bash
# 1. Create the identity in Infisical (web UI or CLI)
#    Infisical → Machine Identities → Create → name: andrew-hermes
#    Note the clientId shown on the identity page.

# 2. Mint a client secret (shown once — copy it now)
#    Infisical → Machine Identities → andrew-hermes → Client Secrets → Add

# 3. Fill in the scope manifest (already in the omnimcp repo — just needs clientId)
#    scopes/andrew-hermes.yaml → replace FILL_IN with clientId
#    git commit + push → hot-reload on server:
#      docker compose kill -s SIGHUP omnimcp
```

## Wire into Hermes config

Add to `~/.hermes/config.yaml` under `mcp_servers`:

```yaml
mcp_servers:
  omnimcp:
    url: "https://mcp.theochinomona.tech/mcp"
    headers:
      X-Infisical-Client-Id: "<andrew-hermes clientId>"
      X-Infisical-Client-Secret: "<andrew-hermes clientSecret>"
```

Then restart the gateway:

```bash
systemctl --user restart hermes-gateway.service
```

## Tools Andrew gets

| Tool | What it does |
|------|-------------|
| `firecrawl.scrape` | Scrape a prospect/company URL |
| `firecrawl.search` | Web search via Firecrawl |
| `firecrawl.extract` | Structured extraction from a page |
| `firecrawl.map` | Crawl a site and return all URLs |
| `n8n.search_workflows` | Find automation workflows by name |
| `n8n.execute_workflow` | Trigger a workflow |
| `n8n.get_workflow_details` | Inspect a workflow |
| `n8n.get_execution` | Check execution result |
| `vault.get_secret` | Read a secret from Infisical |
| `vault.list_secrets` | List available secrets |
| `pg.captureiq.list_opportunities` | List pipeline opportunities |
| `pg.captureiq.get_opportunity` | Get a specific opportunity |
| `pg.captureiq.list_pursuits` | List active pursuits |
| `pg.captureiq.list_tasks` | List tasks |
