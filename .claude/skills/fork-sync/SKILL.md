# fork-sync

**Type:** Claude Code dev skill
**Purpose:** Pull upstream (NousResearch) commits into the fork's `main` branch and push to `theo` remote.

## Triggers
- "sync upstream"
- "sync fork"
- "pull upstream changes"
- "upstream has updates"
- "get latest from NousResearch"

## Steps

1. **Fetch both remotes**
   ```
   git fetch origin
   git fetch theo
   ```

2. **Fast-forward local main**
   ```
   git checkout main
   git merge origin/main --ff-only
   ```
   - If `--ff-only` fails, the fork's main has diverged — do NOT force merge. Stop and report to Theo.

3. **Push to fork**
   ```
   git push theo main
   ```

4. **Report** — show how many commits were synced (`git log --oneline ORIG_HEAD..main`)

## Safety

- Only ever fast-forward `main` — never rebase or merge onto it manually.
- Never push to `origin` (NousResearch upstream).
- If main has diverged from upstream, stop and flag it rather than resolving silently.
