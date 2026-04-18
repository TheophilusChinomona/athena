# fork-pr

**Type:** Claude Code dev skill
**Purpose:** Open a pull request from the current branch against `TheophilusChinomona/hermes-agent` main, after ensuring the branch is synced and rebased.

## Triggers
- "create PR"
- "open pull request"
- "raise PR on fork"
- "PR to the fork"

## Pre-flight

Before opening, confirm:
1. Branch is rebased on latest `main` (run `fork-sync` + `fork-rebase` first if unsure)
2. No uncommitted changes — commit or stash them
3. Branch is pushed to `theo` remote

## Steps

1. **Collect commits** for the PR description:
   ```
   git log main..HEAD --oneline
   ```

2. **Create PR** via `gh`:
   ```
   gh pr create \
     --repo TheophilusChinomona/hermes-agent \
     --base main \
     --head <branch> \
     --title "<type>: <short summary>" \
     --body "..."
   ```

3. **PR body format**:
   ```markdown
   ## Summary
   - bullet per logical change

   ## Test plan
   - [ ] item per change worth verifying

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

4. **Return the PR URL** to Theo.

## Safety

- Always target `TheophilusChinomona/hermes-agent`, never `NousResearch/hermes-agent`.
- One PR per feature branch — don't stack unrelated commits into a single PR.
