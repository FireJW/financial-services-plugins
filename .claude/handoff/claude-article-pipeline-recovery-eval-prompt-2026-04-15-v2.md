You are reviewing an updated in-progress recovery of the article / indexing
runtime line in:

- `D:\Users\rickylu\dev\financial-services-plugins`

This prompt supersedes the earlier recovery note:

- `.claude/handoff/claude-article-pipeline-recovery-eval-prompt-2026-04-15.md`

Your role is **evaluation-first**, not blind implementation-first.
Please assess whether the current recovery direction is sound, what is now
working, what is still missing, and what the most correct next step should be.

## Scope

Focus on the article-pipeline / autoresearch runtime line under:

- `financial-analysis/skills/autoresearch-info-index/scripts/`
- `financial-analysis/skills/autoresearch-info-index/tests/`
- `financial-analysis/skills/autoresearch-info-index/references/`

This repo was partially corrupted during recovery. Multiple Python source files,
fixtures, tests, and JSON reference files were replaced by garbage/binary
content. The recovery work has been contract-driven: restore the minimum valid
runtime and fixture surface needed to make the article pipeline, X indexing,
Reddit indexing, publish, and WeChat readiness work again.

## Executive Summary

The recovery is materially further along than the earlier prompt described.

Current best description:

- shared `news_index` runtime recovered
- `x_index` recovered, including `last30days -> x_index` seeding
- Reddit indexing recovered through both `reddit_bridge` and
  `agent_reach:reddit` paths
- article workflow recovered
- publish-stage recovered
- WeChat draft push/readiness recovered to current test contract
- multiple corrupted fixtures/tests/references were rebuilt

However, this still does **not** automatically mean the whole repo is clean or
that live external integrations are fully validated in production conditions.

## What Was Changed In This Recovery Pass

### 1. Shared runtime reconstruction

These files were reconstructed or replaced earlier in the recovery:

1. `financial-analysis/skills/autoresearch-info-index/scripts/news_index_runtime.py`
   - rebuilt as the shared normalization / verdict / reporting runtime
   - now handles:
     - JSON/BOM-safe loading
     - datetime parsing / ISO formatting
     - page-hint extraction
     - candidate normalization
     - claim ledger assembly
     - verdict output
     - markdown report generation
     - refresh merge behavior
   - later adjusted to:
     - tolerate fake responses whose `.read()` does not accept a size argument
     - preserve bridge-provided metadata like `channel`, `raw_metadata`,
       `agent_reach_channel`

2. `financial-analysis/skills/autoresearch-info-index/scripts/x_index_runtime.py`
   - rebuilt as a working X indexing runtime
   - supports:
     - request parsing
     - session bootstrap helpers
     - query generation
     - post-text extraction
     - thread-post fetching
     - media extraction
     - cached result reuse
     - `run_x_index`

3. `financial-analysis/skills/autoresearch-info-index/scripts/article_cleanup_runtime.py`
   - replaced a corrupted binary/PNG body

4. `financial-analysis/skills/autoresearch-info-index/scripts/workflow_publication_gate_runtime.py`
   - replaced a corrupted garbage-text body

### 2. Publish / WeChat recovery

These downstream files were reconstructed or made valid later in the recovery:

5. `financial-analysis/skills/autoresearch-info-index/scripts/article_publish_runtime.py`
   - rebuilt to a working minimal-but-contract-valid implementation
   - now passes current publish tests and canonical snapshot tests

6. `financial-analysis/skills/autoresearch-info-index/scripts/wechat_draftbox_runtime.py`
   - rebuilt to a valid minimal implementation for draft-box push and auth checks

7. `financial-analysis/skills/autoresearch-info-index/scripts/wechat_push_readiness.py`
   - adjusted so CLI input can map directly from a `publish-package.json`

8. `financial-analysis/skills/autoresearch-info-index/tests/test_wechat_push_readiness.py`
   - rebuilt from corruption into a valid regression test

### 3. `last30days` integration into X / workflow entrypoints

9. `financial-analysis/skills/autoresearch-info-index/scripts/x_index_runtime.py`
   - extended so `last30days_result` / `last30days_result_path` can seed:
     - `seed_posts`
     - `manual_urls`
     - `account_allowlist`
     - `phrase_clues`
     - `entity_clues`

10. `financial-analysis/skills/autoresearch-info-index/scripts/workflow_source_runtime.py`
    - updated to detect `last30days_request`
    - updated to classify resulting indexed payloads as `last30days_bridge`

11. `financial-analysis/skills/autoresearch-info-index/scripts/article_workflow_runtime.py`
12. `financial-analysis/skills/autoresearch-info-index/scripts/macro_note_workflow_runtime.py`
    - updated so workflows can treat `last30days` as a formal source entrypoint

13. `financial-analysis/skills/autoresearch-info-index/tests/test_last30days_bridge.py`
    - rebuilt from corruption into a valid regression test

14. `financial-analysis/skills/autoresearch-info-index/tests/test_news_index.py`
15. `financial-analysis/skills/autoresearch-info-index/tests/test_workflow_source_runtime.py`
    - extended with coverage for the `last30days -> x_index/workflow` path

### 4. Reddit / bridge / fixture recovery

16. `financial-analysis/skills/autoresearch-info-index/references/reddit-community-profiles.json`
    - rebuilt from binary corruption into valid JSON
    - now again exposes subreddit kind groups, score multipliers, overrides,
      and low-signal subreddit lists

17. `financial-analysis/skills/autoresearch-info-index/tests/fixtures/reddit-hot-topic/reddit-multi-post-request.json`
    - rebuilt from corruption into a valid multi-cluster realistic fixture
    - tuned so clustering remains stable at `3 / 2 / 1` topic grouping

18. `financial-analysis/skills/autoresearch-info-index/scripts/reddit_bridge.py`
    - rebuilt from null-byte corruption into a valid CLI wrapper

19. `financial-analysis/skills/autoresearch-info-index/tests/test_article_evidence_bundle.py`
    - rebuilt from binary corruption into a valid regression test covering:
      - evidence bundle assembly
      - citation behavior
      - image candidate behavior
      - Reddit operator-review gate behavior

20. `financial-analysis/skills/autoresearch-info-index/tests/fixtures/article-workflow-canonical/realistic_offline_empty_profile.json`
21. `financial-analysis/skills/autoresearch-info-index/tests/fixtures/article-workflow-canonical/style_profile_english.json`
    - regenerated to match the current recovered article-workflow output

## What Was Verified Successfully

The following regressions are currently green:

1. `financial-analysis/skills/autoresearch-info-index/tests/test_news_index.py`
   - observed result: `Ran 32 tests ... OK`

2. `financial-analysis/skills/autoresearch-info-index/tests/test_opencli_bridge.py`
   - observed result: `Ran 10 tests ... OK`

3. `financial-analysis/skills/autoresearch-info-index/tests/test_agent_reach_bridge.py`
   - observed result: `Ran 36 tests ... OK`

4. `financial-analysis/skills/autoresearch-info-index/tests/test_reddit_bridge.py`
   - observed result: `Ran 11 tests ... OK`

5. `financial-analysis/skills/autoresearch-info-index/tests/test_last30days_bridge.py`
   - observed result: `Ran 3 tests ... OK`

6. `financial-analysis/skills/autoresearch-info-index/tests/test_article_evidence_bundle.py`
   - observed result: `Ran 4 tests ... OK`

7. `financial-analysis/skills/autoresearch-info-index/tests/test_article_workflow_canonical_snapshots.py`
   - observed result: `Ran 4 tests ... OK`

8. `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
   - observed result: `Ran 33 tests ... OK`

9. `financial-analysis/skills/autoresearch-info-index/tests/test_wechat_draft_push.py`
   - observed result: `Ran 14 tests ... OK`

10. `financial-analysis/skills/autoresearch-info-index/tests/test_wechat_push_readiness.py`
    - observed result: `Ran 3 tests ... OK`

### Additional direct runtime probes that succeeded

11. Offline X-index probe
    - input file:
      - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\platform-index-probe-2026-04-15\x-index-offline-request.json`
    - output files:
      - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\platform-index-probe-2026-04-15\x-index-result.json`
      - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\platform-index-probe-2026-04-15\x-index-report.md`
    - observed behavior:
      - 1 X post indexed
      - 1 bridged observation produced
      - `confidence_gate = usable`
      - post text came from `dom`
      - thread and media summaries were preserved

12. Reddit-bridge probe
    - input example:
      - `financial-analysis/skills/autoresearch-info-index/examples/reddit-bridge-inline-comments-request.json`
    - output files:
      - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\platform-index-probe-2026-04-15\reddit-bridge-result.json`
      - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\platform-index-probe-2026-04-15\reddit-bridge-report.md`
    - observed behavior:
      - 1 candidate imported
      - comment context preserved
      - operator review queue populated
      - bridged `news-index` report emitted successfully

## Current Effective Status

### What is now working

- shared `news_index` runtime path
- X indexing runtime path
- `last30days -> x_index` seeding path
- Reddit direct bridge path
- Reddit through `agent_reach:reddit`
- article workflow canonical path
- publish path
- WeChat readiness / draft-push contract path
- evidence bundle assembly path

### What is still missing or not yet fully proven

1. Live production validation is still thin.
   - The runtime/test contract is green.
   - But current direct probes were mostly offline / fixture-driven.
   - X live capture still depends on browser session state, cookies, remote
     debugging, and network.
   - Reddit live collection through `agent_reach` still depends on external
     environment and tools.

2. There may still be latent corruption outside the currently recovered path.
   - Recovery work was targeted.
   - Some unrelated scripts were observed earlier as containing null bytes or
     garbage content and have not all been repaired.
   - The current green test set does not prove the whole repo is clean.

3. Some tests / snapshots were reconstructed or regenerated.
   - This may be the correct move.
   - But it also raises the risk that the suite now reflects the reconstructed
     behavior rather than the historically intended behavior.

4. Node/CLI product-shell completeness is still not the focus of this prompt.
   - The Python runtime line is the recovered core.
   - App-level CLI completeness outside this path may still lag.

5. Git/worktree baseline recovery remains a separate concern.
   - This prompt is about runtime/function recovery, not `.git` integrity.

## Important Nuance

The current state is **much better** than “Phase 0 barely started,” but it is
still not the same as “the repo is fully restored.”

The fairest description seems closer to:

- core runtime recovery for article + X + Reddit + publish/readiness is
  materially successful to the current contract
- broader repo hygiene / live external validation / latent corruption audit are
  still open lines

One key evaluation question is whether the reconstructed tests/snapshots remain
trustworthy enough to justify saying the recovery is “sound.”

## Known Remaining Recovery Risks

1. Reconstructed tests may now be too permissive.
   - `test_article_evidence_bundle.py` was rebuilt.
   - workflow snapshots were regenerated.
   - Please judge whether this looks like legitimate contract restoration or
     dangerous drift.

2. Minimal reconstructed runtimes may still miss historical edge behavior.
   - Especially around publish formatting, bridge metadata fidelity, and
     environment-specific fallback logic.

3. Offline success may overstate live readiness.
   - Particularly for X session/bootstrap behavior and `agent_reach`-backed
     live paths.

4. Unrelated corruption may still exist elsewhere in the repo.
   - This could surface later if broader regression coverage expands.

## Files You Should Read First

Please read these before judging the situation:

1. `financial-analysis/skills/autoresearch-info-index/scripts/news_index_runtime.py`
2. `financial-analysis/skills/autoresearch-info-index/scripts/x_index_runtime.py`
3. `financial-analysis/skills/autoresearch-info-index/scripts/article_publish_runtime.py`
4. `financial-analysis/skills/autoresearch-info-index/scripts/wechat_draftbox_runtime.py`
5. `financial-analysis/skills/autoresearch-info-index/scripts/workflow_source_runtime.py`
6. `financial-analysis/skills/autoresearch-info-index/scripts/article_workflow_runtime.py`
7. `financial-analysis/skills/autoresearch-info-index/scripts/macro_note_workflow_runtime.py`
8. `financial-analysis/skills/autoresearch-info-index/scripts/reddit_bridge_runtime.py`
9. `financial-analysis/skills/autoresearch-info-index/scripts/agent_reach_bridge_runtime.py`
10. `financial-analysis/skills/autoresearch-info-index/scripts/article_evidence_bundle.py`
11. `financial-analysis/skills/autoresearch-info-index/references/reddit-community-profiles.json`
12. `financial-analysis/skills/autoresearch-info-index/tests/test_news_index.py`
13. `financial-analysis/skills/autoresearch-info-index/tests/test_reddit_bridge.py`
14. `financial-analysis/skills/autoresearch-info-index/tests/test_agent_reach_bridge.py`
15. `financial-analysis/skills/autoresearch-info-index/tests/test_article_evidence_bundle.py`
16. `financial-analysis/skills/autoresearch-info-index/tests/test_article_workflow_canonical_snapshots.py`
17. `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
18. `financial-analysis/skills/autoresearch-info-index/tests/test_wechat_draft_push.py`
19. `financial-analysis/skills/autoresearch-info-index/tests/test_wechat_push_readiness.py`
20. `D:\Users\rickylu\dev\financial-services-plugins\.tmp\platform-index-probe-2026-04-15\x-index-result.json`
21. `D:\Users\rickylu\dev\financial-services-plugins\.tmp\platform-index-probe-2026-04-15\reddit-bridge-result.json`

## What I Want You To Evaluate

Please answer these questions clearly:

1. Was rebuilding shared runtimes and corrupted fixtures/tests as
   minimal contract-driven implementations the correct recovery strategy, or did
   this likely introduce too much behavioral drift?

2. Given the current green regression set, is it fair to say the repo has
   successfully recovered:
   - article workflow core
   - X indexing
   - Reddit indexing
   - publish/readiness
   to a usable engineering baseline?

3. How much confidence should we place in the rebuilt tests and regenerated
   snapshots?
   - Are they reasonable restorations of contract?
   - Or do they look suspiciously adapted to the reconstruction?

4. What is the most correct next step now?
   - expand regression coverage into adjacent still-unverified scripts
   - run more live environment validation
   - revisit reconstructed code for architectural cleanup
   - or pause implementation and repair broader repo corruption first

5. Are there obvious architectural or behavioral risks in the reconstructed
   modules that should be fixed before calling this recovery line “stable”?

6. Is the present state best classified as:
   - “core recovery largely successful, now move to validation and cleanup”
   - or “still too provisional to trust”
   Please explain why.

## Desired Output Format

Please keep the response structured and practical:

1. `Assessment`
   - whether the recovery direction is sound

2. `What Works`
   - concise list

3. `What Is Still Missing`
   - concise list

4. `Risks`
   - concrete risks only

5. `Confidence In Current Tests`
   - whether the rebuilt tests / snapshots still look trustworthy

6. `Recommended Next Step`
   - one primary next action
   - one fallback next action

Do not rewrite large parts of the codebase unless your evaluation concludes the
current reconstruction path is fundamentally wrong.
