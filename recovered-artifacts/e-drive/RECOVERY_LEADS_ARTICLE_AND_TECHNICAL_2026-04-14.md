## Recovery Leads: Article Images And Technical Analysis

Date: 2026-04-14

### 1. Article image / social-card line: strong evidence still present

The article-to-image pipeline is not gone. The strongest surviving evidence is:

- live code still exists under `scripts/social-cards/`
- session history shows active edits there on 2026-04-12 and 2026-04-13
- `.tmp/` still contains generated image/card artifacts and shortlist/article outputs

#### Live code evidence

- `scripts/social-cards/render_xiaohongshu_cards.mjs`
  - supports `--eyebrow`
  - has image-driven cover/layout logic
- `scripts/social-cards/render_wechat_longform_cards.mjs`
  - also has image-driven logic
- `scripts/social-cards/build_social_image_sets.mjs`
  - wires `xhs-eyebrow`
  - calls both xiaohongshu and wechat renderers
  - wraps child-process JSON parsing with contextual parse errors
- `scripts/social-cards/build_social_images_from_live_brief.mjs`
  - carries hero reference style/layout/palette
  - passes `xhs-eyebrow`
  - calls `build_social_image_sets.mjs`
- `scripts/social-cards/build_live_brief_from_article.mjs`
  - explicitly says it closes the gap from article pipeline into social output

#### Session evidence

- worker task on 2026-04-12 explicitly targeted:
  - `scripts/social-cards/render_xiaohongshu_cards.mjs`
  - add optional eyebrow rendering for non-editorial covers
- another worker task targeted:
  - `scripts/social-cards/build_social_image_sets.mjs`
  - `scripts/social-cards/build_social_images_from_live_brief.mjs`
  - improve child JSON parse error handling
- 2026-04-13 handoff material explicitly focused on:
  - reducing AI-like article style
  - making social cards absorb reference images
  - fixing image pass-through from article/live-brief into card output

#### Artifact evidence still on disk

- `.tmp/xhs-us-iran-2026-04-13/...`
  - generated xiaohongshu html/png outputs still exist
- `.tmp/social-cards-regression-check/...`
  - regression-check artifacts still exist

### 2. Technical-analysis shortlist line: partial live code plus strong traces

This line is not cleanly restored, but there is strong evidence it existed and ran.

#### Live code still present

- `tests/test_month_end_shortlist_runtime.py`
  - the test suite still exists
- `tests/test_x_stock_picker_style_runtime.py`
- `tests/test_macro_health_overlay_runtime.py`
- `financial-analysis/skills/x-stock-picker-style/scripts/x_stock_picker_style_runtime.py`
- `financial-analysis/skills/macro-health-overlay/scripts/macro_health_overlay_runtime.py`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_tushare_market.py`
  - includes 10 EMA, MACD, RSI, ATR, turnover-based market data logic

#### Missing-but-proven runtime

- The current live repo does **not** have source `.py` files for:
  - `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist.py`
- But the corresponding compiled bytecode still exists at:
  - `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist_runtime.cpython-312.pyc`
  - `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist.cpython-312.pyc`

This is strong proof the shortlist runtime existed locally and was executed on this machine.

#### Broken-but-important recovered file

- `E:\backup\month_end_shortlist_runtime.py` exists by name and has a timestamp in the relevant window,
  but its content is not Python source. The recovered bytes begin with PNG signature data, so Recuva appears to
  have mismatched the filename to the wrong recovered body.
- Even so, keep it as a recovery lead because the filename and timestamp are meaningful.

#### Runtime artifacts still on disk

- `.tmp/month-end-shortlist-live-smoke/report.md`
- `.tmp/month-end-shortlist-live-smoke/result.json`
- `.tmp/month-end-shortlist-validation/...`
- `.tmp/month-end-shortlist-cache/...`

These prove the shortlist workflow ran and produced structured outputs even though the main source file is currently missing.

### 3. Technical-analysis upgrade line recovered from E-drive sessions

The E-drive archive captured a newer design line that goes beyond classic shortlist scoring:

- `legendary-investor` daily validation upgrade
  - `preopen_auction`
  - `execution_feasibility`
  - volume / turnover / volatility / gap integration
  - momentum and Wyckoff considerations
- `month_end_shortlist` contract review
  - `degraded_mode`
  - enriched path
  - `strict / near_strict / weak_fallback`
  - leg-mapping limitations vs richer ranking logic

### 4. Restored into live project during this recovery pass

The following `legendary-investor` files were restored into the live `obsidian-kb-local` tree because they were
missing and we had high-confidence recovered copies:

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

### 5. Best next recovery targets

If we keep going, the highest-value next targets are:

1. recover or reconstruct `month_end_shortlist_runtime.py`
2. recover or reconstruct `month_end_shortlist.py`
3. recover missing `obsidian-kb-local` companion files:
   - `src/legendary-investor-decision.mjs`
   - `src/legendary-investor-review.mjs`
   - `scripts/legendary-investor-runner.mjs`
   - any handoff JSON files referenced by the trade-plan validation docs
