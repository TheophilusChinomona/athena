# fork-rebase

**Type:** Claude Code dev skill
**Purpose:** Rebase the current feature branch on top of updated `main`, resolve any conflicts, and force-push to `theo` remote.

## Triggers
- "rebase on main"
- "rebase our branch"
- "rebase after sync"
- "update branch with upstream"
- "conflicts after sync"

## Steps

1. **Confirm current branch** — never run this on `main`
   ```
   git branch --show-current
   ```

2. **Rebase**
   ```
   git rebase main
   ```

3. **On conflict** — resolve each file:
   - Read both sides carefully. Understand what upstream changed vs what our commit changed.
   - Merge intent, not just lines — preserve both features if they're additive.
   - After each file: `git add <file>`, then `git rebase --continue`
   - If a conflict is ambiguous, stop and ask Theo before guessing.

4. **Force-push**
   ```
   git push theo <branch> --force-with-lease
   ```
   - Use `--force-with-lease`, never bare `--force`.

5. **Report** — confirm rebase completed cleanly, show new tip commit.

## Safety

- Never rebase `main` itself.
- `--force-with-lease` will fail if theo remote has commits you haven't fetched — run `git fetch theo` first if that happens.
- If rebase produces more than 3 conflicts, stop and review with Theo — something structural may have diverged.
