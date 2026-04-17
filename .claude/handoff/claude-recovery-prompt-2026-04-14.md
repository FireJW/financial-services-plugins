You are continuing a repo-recovery task for the canonical repository at:

- `D:\Users\rickylu\dev\financial-services-plugins`

There is also an older scratch recovery staging copy at:

- `C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins`

Use the D-drive repo as the primary working tree for any new edits.
Only consult the scratch copy when a recovery artifact exists there and has not
yet been copied back.
Do not modify the user's active C-drive Codex home/config as part of this task.
In particular, leave these alone unless the user explicitly asks for config migration:

- `C:\Users\rickylu\.codex\config.toml`
- `C:\Users\rickylu\.codex\.codex-global-state.json`

This is **not** a generic cleanup task. The repo was partially deleted and then partially restored. Your job is to recover high-value local development work with minimal additional damage.

Read first:

1. `.claude/handoff/claude-recovery-handoff-2026-04-14.md`
2. `RESTORE_NOTES_2026-04-14.md`
3. `recovered-artifacts/e-drive/SESSION_HIGHLIGHTS_2026-04-14.md`
4. `recovered-artifacts/e-drive/DEVELOPMENT_TIMELINE_2026-04-14.md`
5. `recovered-artifacts/e-drive/RECOVERY_LEADS_ARTICLE_AND_TECHNICAL_2026-04-14.md`

Also be aware of the promoted focused sibling workspaces:

- `D:\Users\rickylu\dev\financial-services-docs`
- `D:\Users\rickylu\dev\financial-services-stock`
- `D:\Users\rickylu\dev\financial-services-obsidian`

Use them only when a focused workstream is easier there than inside the monorepo.

Then focus on these two lines only:

## Line A: article image / social-card pipeline

Primary live files:

- `scripts/social-cards/render_xiaohongshu_cards.mjs`
- `scripts/social-cards/render_wechat_longform_cards.mjs`
- `scripts/social-cards/build_social_image_sets.mjs`
- `scripts/social-cards/build_social_images_from_live_brief.mjs`
- `scripts/social-cards/build_live_brief_from_article.mjs`
- `scripts/social-cards/visual-style-engine.mjs`
- `tests/social-cards/content-classifier.test.mjs`
- `tests/social-cards/visual-style-engine.test.mjs`
- `tests/social-cards/image-driven-pipeline.test.mjs`

Important runtime artifacts:

- `.tmp/xhs-us-iran-2026-04-13/`
- `.tmp/social-cards-regression-check/`

What to verify:

1. whether the article -> live-brief -> social-image path is complete
2. whether reference-image / hero-image pass-through is still intact
3. whether the current live scripts already contain the latest intended behavior from the recovered sessions
4. what exact gaps remain vs the recovered handoff goals

Do not rewrite this line from scratch unless something is clearly missing.

## Line B: technical-analysis shortlist / validation

Primary live files:

- `tests/test_month_end_shortlist_runtime.py`
- `tests/test_x_stock_picker_style_runtime.py`
- `tests/test_macro_health_overlay_runtime.py`
- `financial-analysis/skills/x-stock-picker-style/scripts/x_stock_picker_style_runtime.py`
- `financial-analysis/skills/macro-health-overlay/scripts/macro_health_overlay_runtime.py`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_tushare_market.py`

Critical missing targets:

1. `month_end_shortlist_runtime.py`
2. `month_end_shortlist.py`
3. likely wrappers:
   - `run_month_end_shortlist.cmd`
   - `run_macro_health_assisted_shortlist.cmd`
   - `run_x_style_assisted_shortlist.cmd`

Critical surviving proof:

- `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist_runtime.cpython-312.pyc`
- `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist.cpython-312.pyc`
- `.tmp/month-end-shortlist-live-smoke/`
- `.tmp/month-end-shortlist-validation/`
- `.tmp/month-end-shortlist-cache/`

Important warning:

- `recovered-artifacts/e-drive/shortlist-recovery-leads/month_end_shortlist_runtime.py` is a wrong-body recovered file and appears to contain PNG data, not Python source.
- Keep it as evidence only. Do not trust it as code.

## `legendary-investor` recovery line

Some `legendary-investor` files were already restored into live `obsidian-kb-local`.
Treat these as real recovered assets, not speculative notes.

Recovered live files now include:

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

Likely still missing:

- `obsidian-kb-local/src/legendary-investor-decision.mjs`
- `obsidian-kb-local/src/legendary-investor-review.mjs`
- `obsidian-kb-local/scripts/legendary-investor-runner.mjs`

Use:

- `recovered-artifacts/e-drive/legendary-investor-raw/`
- `recovered-artifacts/e-drive/reconstructed/obsidian-kb-local/`
- `recovered-artifacts/e-drive/claude-daily-trade-plan-validation-handoff-2026-04-13.md`
- `recovered-artifacts/e-drive/claude-daily-trade-plan-validation-prompt-2026-04-13.md`

## Priority order

1. Preserve and understand before editing.
2. Keep all real edits in the D-drive canonical repo.
3. For the technical-analysis line, recover or reconstruct `month_end_shortlist_runtime.py` first.
4. Then recover or reconstruct `month_end_shortlist.py`.
5. Then fill `legendary-investor` companion gaps.
6. Only then consider smaller contract cleanup on the article/social-card line.

## Recovery strategy

When reconstructing missing code:

1. use live tests as the contract
2. use sibling runtimes as style/shape guidance
3. use `.tmp` outputs as behavioral evidence
4. use E-drive rollout/handoff files as design intent
5. use `.pyc` as a last-resort reverse-engineering lead if no source exists

Do not:

- trust damaged `.git` as the source of truth
- do new primary work in the scratch repo when the D-drive repo already exists
- modify the user's C-drive Codex home/config just to steer future work toward D drive
- overwrite existing live files with partial archive copies unless confidence is high
- invent functionality unsupported by tests, artifacts, or recovered docs

## Expected output

Do real work, not only analysis.

At minimum, try to deliver:

1. a concrete recovery status of the two focus lines
2. one or more recovered or reconstructed missing files if confidence is high
3. a precise list of still-missing items
4. a short note describing what came from:
   - live files
   - archived raw recovery
   - reconstructed inference

If blocked, end with the smallest next step that preserves momentum.

If a result is good enough to keep, ensure it is saved in the D-drive canonical
repo and not left only in the scratch copy.
