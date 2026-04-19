# Claude Handoff: Branch Sync via Option B

Date: `2026-04-18`
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Local branch: `main`
Local HEAD: `6703990b7aa39351b5483da3d1c4c1b5971cf092`
Remote branch: `origin/main`
Remote HEAD: `6e66108918d6477061529ce84408a1c5943df42f`

## Goal

Sync local `main` with `origin/main` using:

```bash
git merge origin/main --allow-unrelated-histories
```

This is the recommended path because:

- local and remote histories have no common ancestor
- force-pushing would discard the remote 48-commit history
- cherry-picking upstream commits would be higher effort and easier to get wrong
- the two sides mostly touch different directories, so a one-time unrelated-history
  merge is the safest way to establish a shared ancestry

## Current facts

- `git status` currently reports:

```text
## main...origin/main [ahead 92, behind 48]
?? docs/superpowers/notes/2026-04-17-claude-handoff-screening-and-coverage.md
```

- There is one untracked file that should be handled before merging:
  - `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\notes\2026-04-17-claude-handoff-screening-and-coverage.md`

- Earlier analysis already established:
  - local and remote have different root commits
  - same initial commit message, different SHA
  - rebase is not appropriate because it turns this into 90+ replayed commits with
    cascading modify/delete conflicts

Reference note:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\notes\2026-04-17-branch-sync-issue.md`

## Recommended execution plan for Claude

### 1. Clean the working tree first

Before merging, Claude should either:

- commit the untracked handoff note, or
- temporarily move/delete it if it is not meant to stay

Do **not** start the merge with a dirty working tree.

### 2. Fetch remote state

Run:

```powershell
git -C 'D:\Users\rickylu\dev\financial-services-plugins-clean' -c safe.directory='D:/Users/rickylu/dev/financial-services-plugins-clean' fetch origin
```

### 3. Merge unrelated histories

Run:

```powershell
git -C 'D:\Users\rickylu\dev\financial-services-plugins-clean' -c safe.directory='D:/Users/rickylu/dev/financial-services-plugins-clean' merge origin/main --allow-unrelated-histories
```

### 4. Resolve conflicts conservatively

Working rule:

- prefer **local** side for:
  - `financial-analysis/`
  - `tests/` related to shortlist/discovery/reporting
  - `docs/superpowers/`

- prefer **remote** side for:
  - `claude-in-office/`
  - `private-equity/`
  - `partner-built/`
  - other upstream framework/plugin areas that do not overlap with local
    trading-system work

If the same file has meaningful edits on both sides, Claude should stop and
summarize the exact conflict instead of guessing.

### 5. Verify after merge

Minimum required verification:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest `
  'D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py' `
  'D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_earnings_momentum_discovery.py' `
  'D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py' `
  'D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_discovery_merge.py' `
  'D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_x_style_assisted_shortlist.py' `
  'D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py' -v
```

If Claude has the same environment as before, expected result should be the
current local baseline for these tests, not a degraded subset.

### 6. Push only after verification

If merge succeeds and tests pass:

```powershell
git -C 'D:\Users\rickylu\dev\financial-services-plugins-clean' -c safe.directory='D:/Users/rickylu/dev/financial-services-plugins-clean' push origin main
```

## What Claude should avoid

- Do **not** use `git pull --rebase`
- Do **not** force-push unless explicitly re-approved after merge fails
- Do **not** discard remote history preemptively
- Do **not** resolve overlaps by blindly taking "theirs" or "ours" repo-wide

## Short prompt to Claude

Use Option B.

1. Clean the working tree first.
2. Fetch `origin`.
3. Merge `origin/main --allow-unrelated-histories`.
4. Prefer local for `financial-analysis/`, shortlist/discovery tests, and
   `docs/superpowers/`.
5. Prefer remote for unrelated upstream framework/plugin directories.
6. If any same-file conflict is non-trivial, stop and summarize it instead of
   guessing.
7. Run the verification test set after merge.
8. Only push if merge and tests both succeed.
