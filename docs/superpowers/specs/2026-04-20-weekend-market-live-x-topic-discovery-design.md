# Weekend Market Live X Topic Discovery Design

**Date:** 2026-04-20  
**Status:** Approved design  
**Scope:** Upgrade `weekend_market_candidate` from manual tagged input into a
live X-driven multi-topic discovery layer

## 1. Goal

Make the weekend market candidate flow capable of noticing live X themes such
as commercial space / satellite-chain discussion without requiring the operator
to pre-tag those themes manually.

The upgraded flow should:

- use repository-native live X ingestion as the default upstream source
- keep Windows signed-session collection on `x_index_runtime +
  remote_debugging`
- infer topics from live X evidence instead of depending only on manually
  supplied `tags`
- recognize commercial-space / satellite-chain discussion as a first-class
  topic family
- emit the top `2-3` weekend themes instead of collapsing to a single winning
  topic

## 2. Root Cause

The current system can ingest live X evidence, but the weekend topic layer is
not actually an open-ended live topic discovery system.

Today:

- `x_index_runtime` can fetch live signed-session X content
- `weekend_market_candidate` does **not** automatically call it
- `weekend_market_candidate` mostly depends on:
  - `x_seed_inputs[*].tags`
  - `x_expansion_inputs[*].theme_overlap`
  - `reddit_inputs[*].theme_tags`
- the runtime then selects:
  - `topic_counter.most_common(1)[0]`

This means:

1. live X evidence exists upstream but is not automatically connected
2. themes not explicitly tagged into the candidate input can be invisible
3. even if a second theme is present, single-topic collapse can hide it

That is why heavy live discussion around commercial space can be present on X
while the weekend topic output appears to "know nothing."

## 3. Design Principle

Do not solve this by adding more hand-maintained tags.

The correct fix is:

- connect live native X evidence into the weekend topic layer
- infer topics from the live evidence pack
- only then let manual tags remain as an override or bootstrap aid

This keeps the X policy consistent with the repo-wide rule that:

- native `x_index_runtime` is the default X route
- `remote_debugging` is the preferred Windows session strategy

## 4. New Input Shape

Extend `weekend_market_candidate_input` so it can accept live X evidence in
addition to the current seed/expansion/reddit rows.

Recommended Phase 1 additions:

- `x_live_index_results`
  - inline structured `x-index` results
- `x_live_index_result_paths`
  - paths to previously produced `x-index` result JSON files

The current fields remain valid:

- `x_seed_inputs`
- `x_expansion_inputs`
- `reddit_inputs`

Priority order:

1. live native `x-index` results
2. reused recent `x-index` result files
3. manual tagged seed / expansion rows
4. Reddit confirmation

The important semantic change is:

- manual tags are no longer the only way a topic enters the weekend candidate

## 5. Topic Inference

Add a topic-inference layer inside `weekend_market_candidate_runtime.py`.

Phase 1 behavior:

- inspect normalized live X evidence text
- infer candidate topics from built-in alias groups
- merge inferred topics with any manually supplied `tags` /
  `theme_overlap` / `theme_tags`

This should produce a shared inferred topic counter rather than relying only on
operator-labeled fields.

## 6. Commercial Space / Satellite Topic Family

Commercial space must become a first-class discoverable topic, not an accidental
alias hidden in another workflow.

Phase 1 should explicitly support at least:

- `satellite_chain`
- `commercial_space`

Suggested alias families include terms such as:

- `卫星`
- `卫星互联网`
- `商业航天`
- `火箭`
- `航天发射`
- `星链`
- `Starlink`
- `SpaceX`
- `satellite`
- `rocket`
- `launch`

This topic family should be usable by:

- weekend market candidate inference
- direction reference mapping
- future social-scanning reuse

## 7. Topic Registry Reuse

The repo already contains theme alias knowledge in
`x-stock-picker-style`.

Phase 1 should avoid creating a second unrelated alias universe.

Recommended direction:

- reuse or extract the theme alias surface already present in
  `x_stock_picker_style_runtime.py`
- add the new commercial-space aliases there or in a shared helper that both
  flows can consume

The goal is:

- one consistent topic vocabulary for X-derived workflows

## 8. Multi-Topic Output

Stop collapsing the weekend candidate to a single topic.

Phase 1 should emit:

- top `2-3` candidate topics

Each topic should still carry:

- `priority_rank`
- `ranking_logic`
- `ranking_reason`
- `key_sources`

But the output should no longer assume:

- only one topic is worth surfacing

This directly addresses cases where:

- optical is still relevant
- oil shipping is still relevant
- commercial space is newly relevant

and all three deserve visibility.

## 9. Ranking Logic

The existing ranking dimensions remain useful:

- `seed_alignment`
- `expansion_confirmation`
- `reddit_confirmation`
- `noise_or_disagreement`

Phase 1 should add one more structural input:

- `live_x_evidence_strength`

This does not need to become a separate public field immediately, but ranking
must clearly reward:

- repeated live X evidence from preferred seeds
- repeated live X evidence from expansion accounts
- repeated matching topic inference from multiple live posts

## 10. Key Sources

`key_sources` should stop being limited to manually entered seed rows.

Phase 1 should allow:

- live X posts captured by `x_index_runtime`
- manual seed rows
- Reddit confirmation rows

Each key source still needs:

- `source_name`
- `source_kind`
- `url`
- `summary`

This is how live commercial-space evidence will become visible in the final
brief instead of remaining trapped in raw X output files.

## 11. Report Placement

The report structure should remain:

1. weekend candidate block
2. direction reference map
3. formal shortlist / decision flow

The change is only that the weekend candidate block becomes:

- live X aware
- multi-topic
- able to show commercial-space if it ranks into the top `2-3`

## 12. Failure Handling

Live X discovery must fail softly.

If live `x-index` input is unavailable:

- fall back to reused `x-index` results if present
- otherwise fall back to manual tagged inputs
- otherwise emit the current insufficient-signal behavior

The weekend candidate layer must not become all-or-nothing because the X path
is temporarily unavailable.

## 13. Success Criteria

This design is successful if:

1. live signed-session X evidence can directly influence weekend topic ranking
2. commercial-space / satellite-chain discussion becomes discoverable without
   manual tag injection
3. the weekend candidate output can surface `2-3` themes instead of only one
4. live X evidence appears in `key_sources`
5. the formal shortlist discipline remains unchanged

## 14. Non-Goals

Phase 1 does not attempt to:

- turn weekend candidate into a full autonomous stock picker
- replace formal shortlist execution logic
- require perfect topic extraction from every X post
- remove manual seed inputs

## 15. Future Extensions

If this works, later phases can add:

- per-theme confidence calibration
- X author weighting based on historical usefulness
- cross-topic clustering across X + Reddit + news
- automatic `direction_reference_map` name generation from discovered topics
