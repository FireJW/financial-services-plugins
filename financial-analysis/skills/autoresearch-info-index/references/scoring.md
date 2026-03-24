# Info Index Scoring

Use a simple 100-point scale.

## Dimensions

- `source_coverage` / 25
  Enough primary or near-primary sources are included for the key claims.
- `claim_traceability` / 20
  Important statements can be traced back to named sources or links.
- `recency_discipline` / 20
  The note makes clear what is current and anchors all relative timing.
- `contradiction_handling` / 15
  The note surfaces disagreements, denials, or lack of confirmation.
- `signal_extraction` / 10
  The note converts noisy reporting into a usable bottom line.
- `retrieval_efficiency` / 10
  The result is easy to scan and reuse later.

## Decision Guidance

Keep the candidate only when:

1. all hard checks pass
2. no unsupported certainty is introduced
3. the candidate improves by at least 2 points

## Credibility Snapshot

Besides the weighted score, capture a separate credibility snapshot for each
evaluated note:

- `source_strength_score`: how strong the source mix is
- `claim_confirmation_score`: how well key claims are directly supported
- `timeliness_score`: how fresh the evidence set is relative to the analysis date
- `agreement_score`: how much the sources and claim states line up
- `confidence_score`: a rolled-up confidence estimate
- `confidence_interval`: a practical uncertainty band around that estimate

These do not replace the main keep-or-rollback rule. They make it easier to
compare information quality across many runs later.

## Retrieval Quality Add-On

The recency-first front half adds a second score block:

- `freshness_capture_score`
- `shadow_signal_discipline_score`
- `source_promotion_discipline_score`
- `blocked_source_handling_score`

These metrics explain whether the retrieval engine is improving even when prose
quality looks similar.

## Ranking Defaults

Use:

`rank_score = source_tier_weight + recency_boost + corroboration_boost - contradiction_penalty - staleness_penalty`

Default source tier weights:

- Tier 0 `official/government/regulator/company filing`: `100`
- Tier 1 `wire/major_news`: `80`
- Tier 2 `specialist/public AIS/public ship-tracker`: `60`
- Tier 3 `social/market_rumor/community`: `35`

Default recency boosts:

- `0-10m`: `+40`
- `10-60m`: `+30`
- `1-6h`: `+20`
- `6-24h`: `+10`
- `>24h`: `+0`

Default contradiction penalties:

- fresh Tier 0/1 contradiction against a weaker claim: `-35`
- fresh same-tier contradiction: `-20`
- stale contradiction older than 24 hours: `-10`

Default corroboration boosts:

- one independent confirmation: `+15`
- two or more confirmations across tiers: `+25`
