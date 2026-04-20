# Positive Feedback Soft Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable soft-preference layer for topic ranking, headline generation, and cover selection based on validated positive feedback signals, without turning any single article pattern into a hard rule.

**Architecture:** Extend the existing ranking and content-generation hooks with small additive scoring and candidate-selection helpers. Preserve all current hard filters and fallback paths; add new signals only as bounded bonuses or preference ordering.

**Tech Stack:** Python, existing `hot_topic_discovery_runtime.py`, `article_draft_flow_runtime.py`, `article_publish_runtime.py`, pytest

---

### Task 1: Add topic positive-feedback signal helpers

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Write the failing tests for topic soft preference**

Add tests that build two close-scoring candidates where one is:
- hard industry
- clear actor
- contrarian/judgment-friendly
- China or market relevant

Assert that:
- it receives a positive-feedback bonus
- it ranks above the generic candidate when base scores are otherwise close

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "positive_feedback_topic" -v`

Expected:
- FAIL because the new helpers and score fields do not exist yet

- [ ] **Step 3: Implement minimal topic signal helpers**

Add helper functions near the scoring section:
- `positive_feedback_topic_signals(candidate)`
- `positive_feedback_topic_bonus(candidate)`

Use existing candidate data only:
- title
- keywords
- source_names
- summary / recommended_angle / why_now if available

Signal families:
- hard industry
- clear actor
- contrarian frame
- China/market relevance

Keep bonus bounded, e.g. max `12`.

- [ ] **Step 4: Add the bonus into score computation**

In the main scoring path:
- compute bonus after base `timeliness/debate/relevance/depth/seo`
- store it under `candidate["score_breakdown"]["positive_feedback_bonus"]`
- add a short reason into `score_reasons`
- add the bonus to `total_score` with clamp

- [ ] **Step 5: Run focused tests again**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "positive_feedback_topic" -v`

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add soft positive-feedback topic preference"
```

### Task 2: Add soft headline-frame preferences

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Write failing tests for eligible Chinese headline frames**

Add tests that:
- provide a Chinese topic with a clear actor and judgment angle
- assert `finalize_article_title()` can prefer a stronger conclusion-style title candidate
- assert ineligible topics still keep plain/generated titles

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "headline_frame" -v`

Expected:
- FAIL because no headline-frame helper exists yet

- [ ] **Step 3: Implement headline eligibility and frame candidate helpers**

Add:
- `headline_frame_eligible(request, source_summary, analysis_brief)`
- `headline_frame_candidates(request, source_summary, analysis_brief)`

Eligible only when:
- language is chinese
- topic has clear named actor/company
- topic is not a plain breaking-news brief / obituary / local filler / feature chat
- derived title length and structure can support a strong frame

Candidate frames should be abstract, such as:
- `X真正的护城河是……`
- `最怕的不是……而是……`

Do not hardcode yesterday’s exact title.

- [ ] **Step 4: Integrate headline frames into title finalization**

In `finalize_article_title()`:
- derive the normal base title first
- if eligible, generate 1-2 frame candidates
- choose the first valid candidate that passes existing compact/hanging-tail safety checks
- fall back to the normal title if none validate

Optionally persist:
- `headline_frame_used` in effective request or article package metadata

- [ ] **Step 5: Run focused tests again**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "headline_frame" -v`

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add soft high-performing headline frames"
```

### Task 3: Add official-photo cover preference ordering

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_publish_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Write failing tests for cover source preference**

Add tests where cover candidates include:
- an official/newsroom real photo
- a generated local illustration

Assert that for semiconductor / AI infra / big-tech-actor topics:
- the official real photo is preferred
- generated image remains fallback, not removed

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "cover_source_preference" -v`

Expected:
- FAIL because source preference scoring does not exist yet

- [ ] **Step 3: Implement cover source preference scoring**

Add helper(s):
- `cover_source_preference_score(candidate, request, selected_topic)`
- optionally `topic_prefers_real_industry_cover(selected_topic, request)`

Heuristics may use:
- `source_name`
- `source_url`
- `path`
- `caption`
- `role`

Preferred ordering:
- official real photo / newsroom image
- article/news image
- generated illustration / synthetic local image

Only apply the boost on relevant topics:
- semiconductors
- AI infrastructure
- big tech companies / named actors

- [ ] **Step 4: Integrate into `select_cover_plan()` ordering**

Do not rewrite the existing fallback tree.
Instead:
- sort dedicated/screenshot/body candidates using preference score first, then current order
- preserve all current explicit override logic

Expose score in `cover_candidates` when useful for debugging.

- [ ] **Step 5: Run focused tests again**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "cover_source_preference" -v`

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_publish_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): prefer official real-photo covers for industry topics"
```

### Task 4: Run regression verification across all touched paths

**Files:**
- Modify: none expected
- Test:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_agent_reach_bridge.py`

- [ ] **Step 1: Run focused article publish regression**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "hot_topic_discovery or headline_frame or cover_source_preference" -v`

Expected:
- PASS

- [ ] **Step 2: Run agent reach regression to ensure topic inputs still normalize correctly**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_agent_reach_bridge.py -v`

Expected:
- PASS

- [ ] **Step 3: Record any unrelated known failures, if present**

If a pre-existing unrelated failure appears, document it explicitly rather than masking it.

- [ ] **Step 4: Commit**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/docs/superpowers/specs/2026-04-19-positive-feedback-soft-preferences-design.md D:/Users/rickylu/dev/financial-services-plugins/docs/superpowers/plans/2026-04-19-positive-feedback-soft-preferences-implementation-plan.md
git commit -m "docs(autoresearch): add soft-preference design and implementation plan"
```

### Task 5: Optional live validation after implementation

**Files:**
- Create/update runtime outputs under:
  - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\`

- [ ] **Step 1: Re-run a live topic shortlist**

Run the existing discovery command/request that produced the most recent shortlist and save output under a new dated `.tmp` directory.

- [ ] **Step 2: Compare before/after**

Check whether:
- industry actor-driven topics receive the soft bonus
- stronger headline candidates appear only for eligible Chinese topics
- official real-photo covers outrank generated covers when both are available

- [ ] **Step 3: Summarize deltas**

Write a short markdown note in the `.tmp` run directory describing:
- what changed
- what did not change
- any remaining overfitting risk

---

## Self-Review

- Spec coverage: the plan covers topic preference, headline preference, and cover preference separately.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: all helper names and file paths are defined consistently across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-positive-feedback-soft-preferences-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
