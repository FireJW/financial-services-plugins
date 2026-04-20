# Topic Discovery Recency And Heat Hardening Design

**Date:** 2026-04-20  
**Status:** Drafted for review  
**Scope:** `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py` and targeted tests only

## 1. Goal

Strengthen the hot-topic discovery layer so it more reliably surfaces:

- truly fresh stories from the last `0-24h`
- stories that are not just recent, but actively heating up now
- continuing stories that still deserve ranking because a new catalyst landed

At the same time, the system should more aggressively demote or filter:

- old stories that are only being recycled
- low-signal single-source chatter
- generic platform discussion that looks noisy but is not genuinely timely

The practical target is simple:

- a `2026-04-19` or `2026-04-20` story with fresh confirmation should outrank a strong but stale `2026-02` story
- old stories should remain eligible only when a new catalyst clearly re-opens them
- operator-facing fields should explain whether a topic is fresh, continuing, or stale

## 2. Problem Statement

The current discovery stack already has:

- weighted score inputs:
  - `timeliness`
  - `debate`
  - `relevance`
  - `depth`
  - `seo`
- a large family of weak-topic filters
- operator-facing summary fields:
  - `why_now`
  - `selection_reason`
  - `risk_flags`
  - `source_mix`

That means the system is not missing freshness entirely. The issue is that freshness is still too soft relative to the rest of the ranking model.

Current failure modes:

1. old stories can keep ranking because debate, relevance, or depth offsets their age too easily
2. "heat" does not distinguish well enough between:
   - live discussion happening now
   - old stories with lingering residual discussion
3. `why_now` and `selection_reason` do not clearly tell the operator whether a topic is:
   - newly breaking
   - actively re-accelerating
   - just old noise with weak new support

This is why stale topics can still feel too competitive in the shortlist, even when the user explicitly wants very recent, high-heat stories.

## 3. Design Principles

### 3.1 Keep the core discovery pipeline intact

This change should not redesign the whole topic discovery system.

It should remain:

- candidate collection
- clustering
- filtering
- weighted ranking
- operator-facing explanation fields

The hardening should sit on top of the current ranking model, not replace it.

### 3.2 Separate freshness from generic "heat"
The model needs explicit room to say:

- this is fresh
- this is stale
- this is stale but newly re-opened
- this is hot right now because multiple recent sources are moving together

That means freshness and heat cannot stay collapsed into one vague signal.

### 3.3 Reward new catalysts, not recycled narratives

A continuing story can still rank well, but only if a fresh catalyst exists. Examples:

- new earnings
- new company guidance
- new rollout city or product expansion
- new policy or regulation step
- new conflict escalation
- new legal event

Without a catalyst, stale stories should lose to new ones by design.

### 3.4 Explain ranking decisions in operator language

The user does not just want the "right" ranking. They also want to understand why a topic is on the list now.

The output should explicitly answer:

- is this genuinely fresh?
- is this a continuing story?
- what made it active again?
- what stale risk remains?

## 4. Proposed Ranking Additions

### 4.1 Freshness Window Bonus

Add a new explicit additive score:

- `freshness_window_bonus`

Suggested behavior:

- `0-6h`: strongest bonus
- `6-24h`: clear positive bonus
- `24-72h`: neutral or near-neutral
- `>72h`: no bonus

This layer exists so the ranking model can more forcefully reward topics that are breaking or accelerating right now.

### 4.2 Stale Story Penalty

Add:

- `stale_story_penalty`

Suggested behavior:

- apply when the freshest support is too old
- apply more strongly when the candidate is:
  - single-source
  - fallback-only
  - platform chatter without stronger confirmation

This prevents debate/relevance/depth from masking the fact that the story is simply old.

### 4.3 Fresh Catalyst Bonus

Add:

- `fresh_catalyst_bonus`

This is the one mechanism that lets older stories remain viable.

It should activate only when the candidate looks like a continuing story and the current cycle contains a recent catalyst such as:

- earnings / guidance
- new operating rollout
- policy or regulation escalation
- legal or geopolitical escalation
- clearly timestamped new source confirmation

The point is not to rescue all old stories. The point is to preserve only the ones that truly became active again.

### 4.4 Near-Window Heat Quality Bonus

Add:

- `near_window_heat_bonus`

This is different from simple discussion count. It should prefer topics whose heat is supported by recent activity, such as:

- multiple recent source items
- multiple recent source families
- recent platform + news combination

This bonus should not reward old stories merely for having accumulated historical chatter.

## 5. Proposed Filtering Changes

### 5.1 Stale Old-Story Gate

Introduce a pre-ranking or post-filter gate for clearly stale candidates:

- if freshest support is `>72h` old and no fresh catalyst is detected, filter out

This is the main answer to the "February stories are effectively useless for current heat" complaint.

### 5.2 Weak-Confirmation Old-Story Gate

If a topic is already outside the core freshness window and also weakly supported, filter it out more aggressively:

- `>24h` and single-source
- `>24h` and fallback-only
- `>24h` and platform-chatter-only

This ensures that stale low-signal topics stop occupying shortlist space.

### 5.3 Continuing-Story Exception

Do not filter older candidates if both are true:

- the topic looks like a continuing story
- a fresh catalyst is present

This preserves legitimate ongoing narratives while still blocking recycled noise.

## 6. Operator-Facing Output Changes

Each ranked topic should expose new fields:

- `freshness_bucket`
- `freshness_reason`
- `heat_bucket`
- `staleness_flags`
- `is_continuing_story`
- `fresh_catalyst_present`

These fields should complement, not replace, existing outputs.

### 6.1 Why Now

`why_now` should become more explicit about freshness. Example directions:

- "This topic moved up because multiple fresh sources landed in the last 12 hours."
- "This is an older story, but a new catalyst re-opened it."
- "Discussion exists, but the latest public confirmation is already stale."

### 6.2 Selection Reason

`selection_reason` should become more operational:

- why this topic is on the board now
- why it beat nearby alternatives
- whether the win came from freshness, near-window heat, or a valid continuing-story catalyst

## 7. Minimal Implementation Surface

Target file:

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`

Expected implementation additions:

- new helper(s) to classify freshness buckets
- new helper(s) to detect continuing stories and fresh catalysts
- new helper(s) to compute:
  - `freshness_window_bonus`
  - `stale_story_penalty`
  - `fresh_catalyst_bonus`
  - `near_window_heat_bonus`
- ranking integration into `score_breakdown`
- new `score_reasons` lines for freshness/staleness decisions
- updated `why_now_summary(...)`
- updated `selection_reason_summary(...)`

Target tests:

- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

## 8. Acceptance Criteria

The design is successful when all of the following are true:

1. a fresh `0-24h` story outranks a stale but otherwise strong `>72h` story
2. a stale story with no fresh catalyst is filtered or clearly penalized
3. a continuing story with a fresh catalyst can still survive and rank
4. operator-facing fields clearly say whether the topic is fresh, continuing, or stale
5. `score_breakdown` exposes the new freshness/staleness adjustments

## 9. Test Plan

Add focused tests for:

1. fresh stories outrank stale stories
2. stale debate-heavy stories still get pushed down
3. continuing stories with fresh catalysts remain eligible
4. weak stale stories are filtered out
5. `why_now` and `selection_reason` explicitly reflect freshness logic

The first pass should stay within existing test files and existing runtime entrypoints. No new testing harness is needed.

## 10. Non-Goals

This change does not:

- redesign article generation
- change publish-package structure
- alter WeChat or Toutiao publishing flows
- introduce live external trend APIs
- add online learning from actual read-count metrics

## 11. Recommended Next Step

After spec approval:

- write an implementation plan focused on one runtime file plus targeted tests
- implement via TDD
- verify with focused hot-topic tests first, then the broader article-publish suite
