# 2026-04-28 Global Headline Priority Hot Topics Design

## Goal

Change the `hot_topic_discovery` mechanism so that a true cross-market headline always ranks first when present, while AI and technology topics continue to fill the sector follow-up layer behind it.

The immediate trigger was a miss on the April 28, 2026 UAE exit from `OPEC` / `OPEC+` headline. The current live snapshot workflow favored AI, semiconductors, data center power, and related infrastructure themes strongly enough that a globally important macro-energy headline failed to surface as the primary story.

## Problem Statement

The current mechanism has two coupled failure modes:

1. Request defaults and fit logic bias discovery toward AI and technology topics.
2. Live snapshot filtering can discard globally important headlines when they do not match AI or technology preference keywords closely enough.

This is not just a ranking issue. It is a pipeline issue:

- the live snapshot request is seeded with AI and semiconductor-heavy query terms
- the preferred keyword set reinforces the same sector bias
- `live_snapshot_fit` can mark broad macro or energy stories as low-fit
- low-fit live snapshot stories are filtered before the final shortlist

That means an absolute headline can disappear before the final ranking step ever has a chance to elevate it.

## User Requirement

Default behavior must now be:

`全市场绝对头条永远排第一，AI/科技只是后面的行业层筛选`

In product terms:

- if a candidate is a true cross-market headline, it must occupy rank 1
- AI and technology relevance must not be a prerequisite for that top slot
- AI and technology topics remain the preferred pool for follow-up ideas after the top headline slot

## Approaches Considered

### Approach A: Keep One Ranked List, Increase Macro Weights

Increase heat, timeliness, and source confirmation for macro stories so they naturally beat sector stories inside the existing single ranking list.

Pros:

- smallest code surface
- preserves one-list mental model

Cons:

- still fragile because AI-biased fit and filtering may remove the story before scoring matters
- hard to guarantee rank 1 for true global headlines
- difficult to explain when a macro headline loses again due to sector keyword mismatch

### Approach B: Add a Dedicated Global Headline Lane Before Sector Ranking

Classify candidates into two layers:

1. `global_headline`
2. `sector_follow_up`

Then rank inside each lane and always emit the best `global_headline` first when one qualifies.

Pros:

- directly encodes the user requirement
- avoids accidental suppression by sector preference logic
- easier to reason about in reports and tests
- preserves the existing AI and tech shortlist behavior for the rest of the list

Cons:

- adds a classification concept to the pipeline
- requires report changes, not just score tuning

### Approach C: Keep One Ranked List but Add a Hard Rank-1 Override

Let the current ranking run as-is, then post-process the ranked candidates and promote a qualifying global headline to rank 1.

Pros:

- moderate code change
- explicit top-slot override

Cons:

- still too late if the candidate was already filtered out
- ranking reasons become harder to explain
- leaves hidden AI bias in the earlier phases untouched

## Recommendation

Use **Approach B**.

It is the smallest design that actually satisfies the requirement end to end. The miss happened before final ranking, so the fix must operate before and during filtering, not only after scoring. A dedicated `global_headline` lane makes the rule durable and testable.

## Design

### 1. Candidate Classification

Introduce a classification pass that assigns each candidate one of:

- `global_headline`
- `sector_follow_up`

The classification should happen after candidate clustering and score breakdown calculation, but before live snapshot filtering removes candidates.

The new classification output should be attached to the candidate, for example:

```json
{
  "headline_priority_class": "global_headline",
  "headline_priority_reason": "cross-market macro-energy shock with broad asset-pricing impact"
}
```

### 2. Global Headline Qualification Rules

A candidate should qualify as `global_headline` only when it satisfies both:

1. **Global importance signal**
2. **Cross-market impact signal**

The intent is to catch events like:

- sovereign or cartel actions with commodity implications
- major central bank or treasury actions
- tariffs, sanctions, capital-control, or trade-policy shocks
- war escalation, shipping choke-point risk, or supply disruption
- major geopolitical decisions with immediate asset-pricing implications

Signals should come from a mix of:

- topic text
- source text
- source confirmation count
- heat and timeliness
- risk and market relevance phrases already available in the candidate payload

This should not be implemented as a giant unbounded classifier. Start with an explicit keyword-and-threshold mechanism, because the failure mode is concrete and the user wants deterministic behavior.

### 3. Global Headline Bypass Rules

If a candidate is classified as `global_headline`, then:

- do **not** demote it for weak AI or tech keyword match
- do **not** drop it through the live snapshot `low_fit` filter
- do **not** apply the `medium_fit` floor to it

However, these rules still remain active:

- explicit excluded keywords
- stale or obviously weak single-source noise filters where the event is not actually confirmed

In other words, the bypass removes sector-bias suppression, not all safety filters.

### 4. Live Snapshot Fit Refinement

The existing `live_snapshot_fit` logic is still useful for the `sector_follow_up` lane, but it must stop acting as the sole gate for whether a topic is shortlist-worthy.

Reframe it as:

- `live_snapshot_fit` continues to decide sector alignment
- `headline_priority_class` decides whether a globally important story bypasses sector fit suppression

That means a candidate can be:

- `headline_priority_class = global_headline`
- `live_snapshot_fit = low_fit`

and still survive to rank 1.

### 5. Ranking Rules

Final shortlist generation becomes two-stage:

1. rank all `global_headline` candidates
2. rank all `sector_follow_up` candidates

Output rules:

- if there is at least one `global_headline`, place the top one at rank 1
- fill the remaining slots from `sector_follow_up`
- if there is no `global_headline`, behave like the current sector-first shortlist

The ranking formula inside `global_headline` can still reuse the existing weighted score, but it should also include a modest boost for cross-market importance so that a weak macro headline does not beat a stronger true one only because of sector-fit remnants.

### 6. Request Default Changes

The current live snapshot request shape over-focuses on AI and semiconductor terms. That is acceptable for the sector-follow-up lane, but not for top-headline recall.

Change the default request behavior so that the effective query strategy has two layers:

- `global_headline_query_terms`
- `sector_follow_up_query_terms`

The sector query terms can remain AI and technology heavy.

The global query terms should always include a compact macro and risk set such as:

- oil
- OPEC
- Fed
- tariff
- sanctions
- war
- shipping
- treasury
- sovereign
- policy shock

This does not mean every report becomes macro-heavy. It means the system always looks for one possible rank-1 cross-market headline before narrowing into sector follow-ups.

### 7. Report Structure

The report should stop pretending everything belongs in one homogeneous ranked list.

New default report structure:

1. `Top Headline Now`
2. `Best Sector Follow-Ups`

`Top Headline Now` should include:

- title
- why it outranks everything else
- market impact reason
- source confirmation summary

`Best Sector Follow-Ups` should include the remaining ranked AI and technology themes, with the same writeability rationale the user already prefers.

This keeps the absolute headline visible without destroying the downstream article ideation workflow.

## Data Flow Impact

The expected runtime order becomes:

1. fetch source items
2. cluster into candidates
3. compute score breakdown
4. compute `live_snapshot_fit`
5. compute `headline_priority_class`
6. apply filters with global-headline bypass rules
7. split into `global_headline` and `sector_follow_up`
8. build final shortlist output
9. render report with separate top-headline and sector-follow-up sections

## Testing Strategy

The change should be driven by focused tests before implementation code is changed.

### Required Red Tests

1. A `UAE exits OPEC/OPEC+` style candidate with high confirmation and high heat but weak AI keyword match must still survive filtering and become rank 1.
2. A strong AI infrastructure candidate should remain ranked behind a qualifying global headline.
3. A macro candidate that is noisy, weakly confirmed, or stale should **not** get promoted just because it contains macro keywords.
4. When no qualifying global headline exists, the current AI and technology shortlist behavior should remain intact.
5. The rendered report should expose `Top Headline Now` separately from `Best Sector Follow-Ups`.

### Regression Focus

Protect against these regressions:

- AI shortlist disappears because macro stories dominate everything
- weak geopolitical chatter jumps ahead of confirmed sector stories
- explicit excluded keywords stop working
- low-fit bypass accidentally disables all live snapshot quality control

## Scope Boundaries

This design does **not** introduce:

- an LLM-based topic classifier
- a generic editorial multi-persona system
- a separate publish workflow
- any change to WeChat push behavior

This is strictly a discovery and ranking mechanism change.

## Success Criteria

The change is successful when:

1. a true global headline like `UAE exits OPEC/OPEC+` reliably surfaces at rank 1
2. AI and technology ideas still dominate the follow-up section when they are the best sector stories
3. the behavior is deterministic and explainable in the report
4. the mechanism is covered by focused tests that fail before the fix and pass after it

## Implementation Notes

The most likely implementation home is the existing `hot_topic_discovery_runtime.py` logic around:

- live snapshot fit classification
- topic controls and filters
- final shortlist construction
- report rendering

Tests should live alongside the existing hot-topic and article publish regression coverage rather than in a new isolated harness.
