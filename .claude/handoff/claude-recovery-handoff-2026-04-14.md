# Handoff: Repo Recovery Focused On Article Images And Technical Analysis

> as of 2026-04-14

## Goal

Continue recovery of high-value deleted local development work for this repo.

The two highest-priority lines are:

1. article-to-image / social-card pipeline
2. technical-analysis-driven stock shortlist / validation pipeline

The objective is not generic cleanup. The objective is to:

- preserve recovered artifacts
- identify what is already back in the live workspace
- identify what is still missing
- recover or reconstruct missing high-value files without corrupting the live tree

## Current State

### Workspace recovery

- The original scratch workspace was rebuilt from multiple recovery sources.
- A stable canonical working copy has now been created at:
  - `D:\Users\rickylu\dev\financial-services-plugins`
- A D-drive backup root has also been created at:
  - `D:\Users\rickylu\repo-safety-backups\financial-services-plugins`
- The scratch repo under `.gemini/antigravity/scratch/` should now be treated as a recovery staging copy, not the primary home for future work.
- The user's active Codex home/config remains on C drive and should be left alone.
- Do not modify:
  - `C:\Users\rickylu\.codex\config.toml`
  - `C:\Users\rickylu\.codex\.codex-global-state.json`
- Git metadata is only partially usable.
- Do not rely on current `.git` for truth about historical state.

See:

- `RESTORE_NOTES_2026-04-14.md`

### Local recovery archive

All high-value E-drive recoveries have been copied into:

- `recovered-artifacts/e-drive/`

Important index files:

- `recovered-artifacts/e-drive/SESSION_HIGHLIGHTS_2026-04-14.md`
- `recovered-artifacts/e-drive/DEVELOPMENT_TIMELINE_2026-04-14.md`
- `recovered-artifacts/e-drive/RECOVERY_LEADS_ARTICLE_AND_TECHNICAL_2026-04-14.md`

These are the durable starting point. Prefer reading them before raw JSONL.

### Promoted D-drive mainlines

Focused sibling workspaces have now been lifted under:

- `D:\Users\rickylu\dev\financial-services-docs`
- `D:\Users\rickylu\dev\financial-services-stock`
- `D:\Users\rickylu\dev\financial-services-obsidian`

Treat them as focused lifted copies for docs / stock / obsidian workstreams.
They do not replace the canonical repo, but they are valid focused entrypoints
for targeted work.

## What Was Recovered

### 1. Article image / social-card line is still alive in live code

Strong live files:

- `scripts/social-cards/render_xiaohongshu_cards.mjs`
- `scripts/social-cards/render_wechat_longform_cards.mjs`
- `scripts/social-cards/build_social_image_sets.mjs`
- `scripts/social-cards/build_social_images_from_live_brief.mjs`
- `scripts/social-cards/build_live_brief_from_article.mjs`
- `scripts/social-cards/visual-style-engine.mjs`
- `tests/social-cards/content-classifier.test.mjs`
- `tests/social-cards/visual-style-engine.test.mjs`
- `tests/social-cards/image-driven-pipeline.test.mjs`

Important evidence already confirmed:

- `render_xiaohongshu_cards.mjs` still supports `--eyebrow`
- image-driven logic still exists for Xiaohongshu and WeChat renderers
- live-brief -> social-image pipeline still exists
- `.tmp/` still contains image/card outputs and regression-check artifacts

### 2. Technical-analysis line is partially alive

Strong live files:

- `tests/test_month_end_shortlist_runtime.py`
- `tests/test_x_stock_picker_style_runtime.py`
- `tests/test_macro_health_overlay_runtime.py`
- `financial-analysis/skills/x-stock-picker-style/scripts/x_stock_picker_style_runtime.py`
- `financial-analysis/skills/macro-health-overlay/scripts/macro_health_overlay_runtime.py`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_tushare_market.py`

Important technical-analysis clues:

- `tradingagents_tushare_market.py` includes:
  - 10 EMA
  - MACD
  - RSI
  - ATR
  - turnover-based market ranking
- E-drive rollout/session material records:
  - turnover / volatility / gap integration work
  - momentum / Wyckoff upgrade direction
  - execution-feasibility / preopen-auction thinking

### 3. `legendary-investor` files were recovered

These recovered files were missing and have already been copied back into the live `obsidian-kb-local` tree:

- `obsidian-kb-local/src/legendary-investor-checklist.mjs`
- `obsidian-kb-local/src/legendary-investor-daily-validation.mjs`
- `obsidian-kb-local/src/legendary-investor-dashboard.mjs`
- `obsidian-kb-local/src/legendary-investor-doctrines.mjs`
- `obsidian-kb-local/src/legendary-investor-reasoner.mjs`
- `obsidian-kb-local/src/legendary-investor-validation-ledger.mjs`
- `obsidian-kb-local/scripts/legendary-investor-decision.mjs`
- `obsidian-kb-local/scripts/legendary-investor-review.mjs`
- `obsidian-kb-local/scripts/legendary-investor-workbench.mjs`
- `obsidian-kb-local/tests/legendary-investor-daily-validation.test.mjs`
- `obsidian-kb-local/tests/legendary-investor-workbench.test.mjs`

Raw recovered originals are also archived under:

- `recovered-artifacts/e-drive/legendary-investor-raw/`

Partial reconstructed tree is archived under:

- `recovered-artifacts/e-drive/reconstructed/obsidian-kb-local/`

## What Is Still Missing

### Highest-value missing files

1. `month_end_shortlist_runtime.py`
2. `month_end_shortlist.py`
3. likely companion command wrappers such as:
   - `run_month_end_shortlist.cmd`
   - `run_macro_health_assisted_shortlist.cmd`
   - `run_x_style_assisted_shortlist.cmd`
4. likely missing `obsidian-kb-local` companions:
   - `obsidian-kb-local/src/legendary-investor-decision.mjs`
   - `obsidian-kb-local/src/legendary-investor-review.mjs`
   - `obsidian-kb-local/scripts/legendary-investor-runner.mjs`

### Strong proof these missing shortlist files existed

Live bytecode still exists:

- `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist_runtime.cpython-312.pyc`
- `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist.cpython-312.pyc`

This means the source files were present and executed locally at some point.

### Important warning

A recovered file named:

- `recovered-artifacts/e-drive/shortlist-recovery-leads/month_end_shortlist_runtime.py`

is **not** valid Python source. Its body begins with PNG signature bytes.
Treat it as a filename/timestamp clue only, not as usable code.

## High-Value Runtime Artifacts Still On Disk

### Social cards / article outputs

- `.tmp/xhs-us-iran-2026-04-13/`
- `.tmp/social-cards-regression-check/`

### Shortlist / technical-analysis outputs

- `.tmp/month-end-shortlist-live-smoke/`
- `.tmp/month-end-shortlist-validation/`
- `.tmp/month-end-shortlist-cache/`

These are useful for reverse-engineering output contracts and expected behavior.

## Recovery Priorities

### Priority 1: shortlist runtime reconstruction

Recover or reconstruct:

- `month_end_shortlist_runtime.py`
- `month_end_shortlist.py`

Best sources to combine:

1. live tests under `tests/`
2. live sibling runtimes:
   - `x_stock_picker_style_runtime.py`
   - `macro_health_overlay_runtime.py`
   - `tradingagents_tushare_market.py`
3. E-drive rollout/session notes in `recovered-artifacts/e-drive/`
4. live `.tmp/month-end-shortlist-*` output artifacts
5. live `.pyc` files under `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/`

### Priority 2: `legendary-investor` companion gap fill

Recover or reconstruct:

- `obsidian-kb-local/src/legendary-investor-decision.mjs`
- `obsidian-kb-local/src/legendary-investor-review.mjs`
- `obsidian-kb-local/scripts/legendary-investor-runner.mjs`

Use:

- restored `workbench`, `daily-validation`, `reasoner`, and tests
- archived raw files under `recovered-artifacts/e-drive/legendary-investor-raw/`
- E-drive handoff docs for expected workflow and CLI behavior

### Priority 3: article/social-card contract hardening

Do not rewrite the whole system. First verify what already exists:

- `--eyebrow`
- image-driven layouts
- hero-ref / live-brief pass-through
- parse-error hardening in social-image build scripts

Then only fill genuine gaps.

## Constraints

- Do not trust damaged git history as the primary source.
- Prefer local archive + live files + `.tmp` artifacts over raw speculation.
- Prefer the D-drive canonical repo over the scratch repo for any new edits.
- Do not change the user's C-drive Codex home/config just to enforce D-drive development.
- Do not overwrite existing live files blindly when a recovered version is only partial.
- Keep every recovered original file archived even if you also reconstruct a cleaner live version.
- If a file is reconstructed from tests / artifacts / `.pyc`, label that clearly in comments or handoff notes.

## Suggested Read Order

1. `D:\Users\rickylu\dev\financial-services-plugins\RESTORE_NOTES_2026-04-14.md`
2. `D:\Users\rickylu\dev\financial-services-plugins\recovered-artifacts\e-drive\SESSION_HIGHLIGHTS_2026-04-14.md`
3. `D:\Users\rickylu\dev\financial-services-plugins\recovered-artifacts\e-drive\DEVELOPMENT_TIMELINE_2026-04-14.md`
4. `D:\Users\rickylu\dev\financial-services-plugins\recovered-artifacts\e-drive\RECOVERY_LEADS_ARTICLE_AND_TECHNICAL_2026-04-14.md`
5. live `scripts/social-cards/*` under the D-drive canonical repo
6. live shortlist / technical-analysis tests under `tests/` in the D-drive canonical repo
7. live technical-analysis runtimes under `financial-analysis/skills/*/scripts/` in the D-drive canonical repo
8. restored `obsidian-kb-local/src/legendary-investor-*` in the D-drive canonical repo
9. archived rollout/handoff raw files as needed

## Recommended Operating Mode

For future work:

1. do all real edits in:
   - `D:\Users\rickylu\dev\financial-services-plugins`
2. use the promoted siblings when a narrower scope is helpful:
   - docs: `D:\Users\rickylu\dev\financial-services-docs`
   - stock: `D:\Users\rickylu\dev\financial-services-stock`
   - obsidian: `D:\Users\rickylu\dev\financial-services-obsidian`
3. only return to the scratch repo if a recovery artifact exists there and has
   not yet been copied back
4. leave Codex's local home/config on C drive unless the user explicitly asks
   for a config migration

## Definition Of Done For The Next Operator

Good next progress means at least one of these happens:

1. `month_end_shortlist_runtime.py` is recovered or reconstructed into a usable live file
2. `month_end_shortlist.py` is recovered or reconstructed into a usable live file
3. `legendary-investor` companion files are reconstructed enough for the validation chain to run
4. missing behavior is proven from `.tmp` artifacts and encoded into reconstructed source/tests
