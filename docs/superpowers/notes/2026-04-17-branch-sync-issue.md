# Branch Sync Issue — Local main vs origin/main

Date: 2026-04-17
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Remote: `origin` → `https://github.com/FireJW/financial-services-plugins.git`

## Problem

`git push origin main` fails with non-fast-forward. `git pull --rebase` loses local work. Root cause: **local `main` and `origin/main` have no common ancestor** — they are two independent git histories that happen to share a repo.

## Evidence

```
git merge-base main origin/main  →  exit code 1 (no common ancestor)

Local main root:  c6b0a6c  "Initial commit: copy from fsi-plugins-dev"
Remote main root: b891783  "Initial commit: copy from fsi-plugins-dev"
```

Same commit message, different SHA — the repo was initialized twice independently.

## Commit counts

| Branch | Total commits | Unique (not in other) |
|--------|--------------|----------------------|
| Local `main` | 91 | 91 |
| `origin/main` | 48 | 48 |

Zero overlap. Every commit is unique to its branch.

## What's on each side

**Local `main` (91 commits):** All local development work:
- financial-analysis (month-end-shortlist, earnings-momentum-discovery, autoresearch)
- Trading report dual-mode, decision factors, x-style discovery
- Screening coverage optimization (the 6 newest commits, cherry-picked from `feat/migrate-trading-optimization`)
- Handoff docs, specs, plans

**`origin/main` (48 commits):** Upstream anthropics plugin framework updates:
- claude-in-office plugin, bootstrap, gateway auth
- manifest validators (otlp, Azure AI Foundry)
- PowerPoint skills, private-equity ai-readiness
- partner-built plugins (LSEG, S&P Global)
- dcf-model, clean-data-xls skills

The two sides modify **completely different directories** — local work is in `financial-analysis/` and `docs/`, upstream work is in `claude-in-office/`, `private-equity/`, `partner-built/` etc.

## Why rebase fails

Attempted `git pull --rebase origin main`. The rebase replays local commits on top of remote history. Since remote history has no `financial-analysis/` files at all, every local commit that touches those files hits a modify/delete conflict. With 91 commits to replay, the conflicts cascade and local work gets dropped.

Concrete failure: rebase replayed only 8 of 91 local commits successfully. The other 83 (containing all `financial-analysis/` code, tests, and scripts) were lost to modify/delete conflicts.

## Files at stake

Critical local-only files that do NOT exist on `origin/main`:
- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`
- `financial-analysis/skills/autoresearch-info-index/scripts/*.py`
- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_*.py`
- `tests/test_x_style_assisted_shortlist.py`
- `tests/test_screening_coverage_optimization.py` (new)
- All files under `docs/superpowers/`

## Current state

- Local `main` at `77679e9` — fully intact, 87 tests pass, includes screening optimization
- `feat/migrate-trading-optimization` — original dev branch, preserved
- `origin/main` at `6e66108` — untouched, still diverged
- No data loss occurred — rebase was aborted and reset to pre-rebase state

## Recommended fix

### Option A: Force push (simplest)

```bash
git push --force-with-lease origin main
```

Overwrites remote with local history. Safe because:
- The 48 upstream commits are framework code unrelated to local work
- Upstream updates can be re-merged from `anthropics/financial-services-plugins` later
- No other collaborators are actively working on this fork's `main`

### Option B: Merge with `--allow-unrelated-histories`

```bash
git fetch origin
git merge origin/main --allow-unrelated-histories
# Resolve conflicts — should be few since different directories
git push origin main
```

Keeps both histories. Results in a merge commit with two root commits. Cleaner provenance but uglier history.

### Option C: Cherry-pick upstream onto local

```bash
# Identify upstream-only commits that touch files we care about
git log --oneline origin/main -- claude-in-office/ private-equity/ partner-built/
# Cherry-pick those onto local main
git cherry-pick <commit-list>
git push --force-with-lease origin main
```

Selective: pick only the upstream commits that matter, apply to local history, then force push.

## Verification after sync

```bash
# All screening optimization tests pass
pytest tests/test_screening_coverage_optimization.py -v

# All related tests pass
pytest tests/test_screening_coverage_optimization.py tests/test_earnings_momentum_discovery.py tests/test_month_end_shortlist_degraded_reporting.py tests/test_month_end_shortlist_discovery_merge.py tests/test_x_style_assisted_shortlist.py tests/test_month_end_shortlist_profile_passthrough.py -v

# Expected: 87 passed
```
