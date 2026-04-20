# Weekend Market Live X Topic Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `weekend_market_candidate` so live native `x-index` evidence
can drive multi-topic weekend discovery, including commercial-space /
satellite-chain visibility.

**Architecture:** Extend `weekend_market_candidate_input` to accept live
`x-index` result payloads or result paths, infer topics from live X evidence
using a shared alias registry, support explicit commercial-space topic aliases,
and emit the top `2-3` ranked weekend themes instead of collapsing to a single
topic. Preserve existing report placement and keep the formal shortlist
execution layer unchanged.

**Tech Stack:** Python 3.12, `month-end-shortlist` runtime,
`autoresearch-info-index` / `x_index_runtime`, existing `x-stock-picker-style`
theme alias surface, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
  - accept live `x-index` inputs
  - infer topics from live X evidence
  - emit top `2-3` topics instead of one
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - preserve passthrough / rendering contract for richer multi-topic weekend
    output
- Modify: `financial-analysis/skills/x-stock-picker-style/scripts/x_stock_picker_style_runtime.py`
  - add or expose commercial-space / satellite aliases if the shared registry
    lives here
- Modify: `tests/test_weekend_market_candidate_runtime.py`
  - add focused inference and multi-topic tests
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
  - lock request/result passthrough for the new live X input fields
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - lock weekend report rendering for top `2-3` themes and live `key_sources`

### Responsibility Boundaries

- `x_index_runtime` remains the native X ingestion layer.
- `weekend_market_candidate_runtime.py` becomes the weekend topic inference
  layer.
- The formal shortlist and `T1` execution rules must remain unchanged.

---

## Task 1: Add Failing Tests for Live X Inputs and Multi-Topic Output

**Files:**
- Modify: `tests/test_weekend_market_candidate_runtime.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Add a failing normalization test**

Cover new accepted input shapes:

- `x_live_index_results`
- `x_live_index_result_paths`

Verify they normalize without dropping existing:

- `x_seed_inputs`
- `x_expansion_inputs`
- `reddit_inputs`

- [ ] **Step 2: Add a failing inference test for commercial space**

Use a small live-X-shaped payload whose text mentions:

- `商业航天`
- `卫星`
- `SpaceX`

Expected:

- topic inference includes `satellite_chain` or `commercial_space`

- [ ] **Step 3: Add a failing multi-topic output test**

Provide mixed live evidence for three themes, for example:

- optical interconnect
- oil shipping
- commercial space

Expected:

- output includes top `2-3` `candidate_topics`
- `priority_rank` values are ordered
- no single-topic collapse

- [ ] **Step 4: Run the focused tests and confirm failure**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

Expected:

- failures because live X input inference and multi-topic output do not yet
  exist

---

## Task 2: Add Live X Input Support to Weekend Candidate Runtime

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`

- [ ] **Step 1: Extend input normalization**

Support:

- `x_live_index_results`
- `x_live_index_result_paths`

Normalization should:

- keep the fields lightweight
- allow either inline results or paths
- avoid breaking current manual input behavior

- [ ] **Step 2: Add reusable extraction helpers**

Add helpers that can:

- read `x-index` result paths
- iterate the normalized live X records
- extract reusable text snippets, author labels, URLs, and metadata

- [ ] **Step 3: Fail softly**

If a supplied path is missing or malformed:

- ignore that path safely
- continue processing any other valid live inputs

---

## Task 3: Implement Topic Inference from Live X Evidence

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
- Modify: `financial-analysis/skills/x-stock-picker-style/scripts/x_stock_picker_style_runtime.py` if alias reuse requires it

- [ ] **Step 1: Build a shared or reused topic alias surface**

Support at least:

- `optical_interconnect`
- `oil_shipping`
- `satellite_chain`
- `commercial_space`

Commercial-space aliases should include terms such as:

- `商业航天`
- `卫星`
- `卫星互联网`
- `火箭`
- `航天发射`
- `星链`
- `SpaceX`
- `satellite`
- `rocket`
- `launch`

- [ ] **Step 2: Infer topics from live X text**

For each live X record:

- scan text against alias groups
- accumulate topic counts / evidence strength
- preserve URLs and source labels for later `key_sources`

- [ ] **Step 3: Merge live inference with manual tags**

Manual tags should remain valid, but live inference should be able to add
topics that were never manually tagged.

---

## Task 4: Upgrade Weekend Output from One Topic to Top 2-3 Topics

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`

- [ ] **Step 1: Remove single-topic collapse**

Replace:

- `topic_counter.most_common(1)[0]`

with a bounded top-topic list such as:

- `topic_counter.most_common(3)`

- [ ] **Step 2: Emit multiple `candidate_topics`**

Each topic still needs:

- `priority_rank`
- `ranking_logic`
- `ranking_reason`
- `key_sources`

- [ ] **Step 3: Keep top-level summary fields usable**

Define a consistent Phase 1 behavior for:

- `beneficiary_chains`
- `priority_watch_directions`
- `signal_strength`

when multiple topics are present

---

## Task 5: Upgrade `key_sources` to Use Live X Evidence

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`

- [ ] **Step 1: Allow live X-derived `key_sources`**

Each source should still expose:

- `source_name`
- `source_kind`
- `url`
- `summary`

Valid source kinds now include:

- `x_seed`
- `x_expansion`
- `x_live_index`
- `reddit_confirmation`

- [ ] **Step 2: Ensure commercial-space evidence can appear directly**

If the commercial-space topic ranks into the top `2-3`, at least one live
commercial-space X post should be eligible for `key_sources`.

---

## Task 6: Preserve Report Placement and Passthrough

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Preserve report placement**

The weekend block must still render:

1. before formal decision flow
2. separate from execution tiers

- [ ] **Step 2: Update markdown expectations for multi-topic rendering**

Add regressions that check:

- top `2-3` topics appear
- ranking logic and `key_sources` remain readable
- commercial-space can appear as a visible weekend topic

---

## Task 7: Verification Ladder

- [ ] **Step 1: Focused weekend runtime tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

- [ ] **Step 2: Weekend rendering regression**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

- [ ] **Step 3: Real live-X smoke**

Use real signed-session `x_index_runtime` results for at least:

- a commercial-space / satellite-chain post set
- one existing known theme such as optical or oil shipping

Then feed those results into `weekend_market_candidate` and verify:

- commercial-space becomes visible without manual topic tags
- the output contains `2-3` ranked weekend themes
- live X posts appear inside `key_sources`

---

## Task 8: Completion Criteria

- [ ] live `x-index` results can feed weekend topic discovery directly
- [ ] commercial-space / satellite-chain is a recognized topic family
- [ ] weekend output no longer collapses to a single topic
- [ ] `key_sources` can contain live X evidence
- [ ] focused verification passes
- [ ] at least one real live-X smoke proves commercial-space visibility
