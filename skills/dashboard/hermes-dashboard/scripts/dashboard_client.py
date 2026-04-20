#!/usr/bin/env python3
"""
Hermes Dashboard Client
Generic CLI/library for interacting with any Hermes dashboard deployment.

Usage:
  python3 dashboard_client.py today
  python3 dashboard_client.py approvals
  python3 dashboard_client.py approve <slug> [note]
  python3 dashboard_client.py reject <slug> [note]
  python3 dashboard_client.py rewrite <slug> [note]
  python3 dashboard_client.py vault [drafts|media]
  python3 dashboard_client.py activity [search_query]
  python3 dashboard_client.py pipeline

Config (env or ~/.hermes/.env):
  HERMES_DASHBOARD_URL    Required. Base URL of the dashboard.
  HERMES_DASHBOARD_TOKEN  Optional. Bearer token for auth.
"""

import os
import sys
import json
from pathlib import Path

try:
    import httpx
except ImportError:
    import urllib.request
    import urllib.error
    httpx = None


def load_env():
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()


def get_config():
    load_env()
    url = os.environ.get("HERMES_DASHBOARD_URL", "").rstrip("/")
    if not url:
        print("ERROR: HERMES_DASHBOARD_URL not set. Add it to ~/.hermes/.env", file=sys.stderr)
        sys.exit(1)
    token = os.environ.get("HERMES_DASHBOARD_TOKEN", "")
    return url, token


def headers(token: str) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get(path: str) -> dict | list:
    url, token = get_config()
    if httpx:
        r = httpx.get(f"{url}{path}", headers=headers(token), timeout=10)
        r.raise_for_status()
        return r.json()
    else:
        req = urllib.request.Request(f"{url}{path}", headers=headers(token))
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())


def post(path: str, body: dict) -> dict:
    url, token = get_config()
    data = json.dumps(body).encode()
    if httpx:
        r = httpx.post(f"{url}{path}", content=data, headers=headers(token), timeout=10)
        r.raise_for_status()
        return r.json()
    else:
        req = urllib.request.Request(f"{url}{path}", data=data, headers=headers(token), method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())


# ── Today ────────────────────────────────────────────────────────────────────

def cmd_today():
    data = get("/api/today")
    print(f"\n{data.get('date', 'Today')}")
    print(f"{data.get('blurb', '')}\n")

    sessions = data.get("sessions", {})
    if sessions:
        print(f"  Sessions: {sessions.get('sessionCount', 0)}  "
              f"Time: {sessions.get('totalMinutes', 0)}m  "
              f"Tool calls: {sessions.get('toolCalls', 0)}")

    crons = data.get("cronRuns", [])
    if crons:
        print(f"\n  Cron runs ({len(crons)}):")
        for c in crons:
            print(f"    {c.get('runAt', '')[:16]}  {c.get('jobName', c.get('jobId', '?'))}  {c.get('status', '?')}")

    pending = data.get("pendingDrafts", [])
    if pending:
        print(f"\n  Awaiting approval ({len(pending)}):")
        for d in pending:
            print(f"    [{d.get('channel', '?')}]  {d.get('displayTitle', d.get('slug', '?'))}")

    sent = data.get("sentToday", [])
    if sent:
        print(f"\n  Sent today ({len(sent)}):")
        for s in sent:
            print(f"    {s.get('channel', '?')}  {s.get('displayTitle', s.get('slug', '?'))}")


# ── Approvals ────────────────────────────────────────────────────────────────

def cmd_approvals():
    items = get("/api/approvals")
    if not items:
        print("Nothing pending.")
        return
    print(f"\n{len(items)} pending approval(s):\n")
    for i, d in enumerate(items, 1):
        tier = d.get("signalTier", "")
        print(f"  {i:02d}. [{d.get('channel', '?')}] {d.get('displayTitle', d.get('slug', '?'))}"
              + (f"  ({tier})" if tier else ""))
        if d.get("subject"):
            print(f"       Subject: {d['subject']}")
        if d.get("excerpt"):
            print(f"       {d['excerpt'][:120]}")
        print(f"       slug: {d.get('slug', '?')}")
        print()


def cmd_decide(slug: str, decision: str, note: str = ""):
    result = post("/api/approvals", {
        "slug": slug,
        "decision": decision,
        "reviewer": os.environ.get("HERMES_REVIEWER", "agent"),
        "note": note,
    })
    if result.get("ok"):
        print(f"✓ {decision}: {slug}")
    else:
        print(f"✗ Failed: {result}")
        sys.exit(1)


# ── Vault ────────────────────────────────────────────────────────────────────

def cmd_vault(sub: str = "drafts"):
    if sub == "media":
        items = get("/api/vault/media")
        print(f"\n{len(items)} media files:\n")
        for m in items:
            size = m.get("size", 0)
            size_str = f"{size // 1024}KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f}MB"
            print(f"  [{m.get('type', '?'):5}]  {m.get('name', '?')}  ({size_str})")
    else:
        items = get("/api/vault/drafts")
        print(f"\n{len(items)} drafts:\n")
        for d in items:
            print(f"  {d.get('status', '?'):20}  [{d.get('channel', '?'):10}]  {d.get('displayTitle', d.get('slug', '?'))}")


# ── Activity ─────────────────────────────────────────────────────────────────

def cmd_activity(query: str = ""):
    path = f"/api/activity?q={query}" if query else "/api/activity"
    data = get(path)
    messages = data if isinstance(data, list) else data.get("messages", [])
    sessions = data.get("sessions", []) if isinstance(data, dict) else []

    if sessions:
        print(f"\n{len(sessions)} session(s):\n")
        for s in sessions:
            print(f"  {s.get('started_at', '')[:16]}  {s.get('message_count', 0)} messages  "
                  f"{s.get('tool_calls', 0)} tool calls")

    if messages:
        print(f"\n{len(messages)} message(s):\n")
        for m in messages[:20]:
            role = m.get("role", "?")
            content = str(m.get("content", ""))[:120]
            print(f"  [{role:9}]  {content}")


# ── Pipeline ─────────────────────────────────────────────────────────────────

def cmd_pipeline():
    data = get("/api/pipeline")
    companies = data if isinstance(data, list) else data.get("companies", [])
    print(f"\n{len(companies)} pipeline companies:\n")
    for c in companies:
        stage = c.get("stage") or c.get("pipeline_stage") or "?"
        name = c.get("name") or c.get("company_name") or "?"
        geo = c.get("geography") or c.get("country") or ""
        print(f"  {stage:20}  {name}" + (f"  ({geo})" if geo else ""))


# ── CLI ──────────────────────────────────────────────────────────────────────

COMMANDS = {
    "today": (cmd_today, []),
    "approvals": (cmd_approvals, []),
    "approve": (cmd_decide, ["slug", "APPROVED"]),
    "reject": (cmd_decide, ["slug", "REJECTED"]),
    "rewrite": (cmd_decide, ["slug", "REWRITE"]),
    "vault": (cmd_vault, []),
    "activity": (cmd_activity, []),
    "pipeline": (cmd_pipeline, []),
}


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    rest = args[1:]

    if cmd == "approve" and rest:
        note = rest[1] if len(rest) > 1 else ""
        cmd_decide(rest[0], "APPROVED", note)
    elif cmd == "reject" and rest:
        note = rest[1] if len(rest) > 1 else ""
        cmd_decide(rest[0], "REJECTED", note)
    elif cmd == "rewrite" and rest:
        note = rest[1] if len(rest) > 1 else ""
        cmd_decide(rest[0], "REWRITE", note)
    elif cmd == "vault":
        cmd_vault(rest[0] if rest else "drafts")
    elif cmd == "activity":
        cmd_activity(" ".join(rest))
    elif cmd in COMMANDS:
        fn, _ = COMMANDS[cmd]
        fn()
    else:
        print(f"Unknown command: {cmd}\n{__doc__}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
