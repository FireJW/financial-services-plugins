# Weekend Market Candidate Design

**Date:** 2026-04-19  
**Status:** Approved design  
**Scope:** `month-end-shortlist` adjacent wrapper/reporting layer only

## 1. Goal

Add a non-trading-day `weekend_market_candidate` layer so weekend X and Reddit
activity can be distilled into a Monday-prep reference block even when live A-share
data is unavailable or intentionally de-emphasized.

The target behavior is:

- weekend X discussion is treated as the primary signal source
- operator-preferred X accounts act as high-weight seeds
- one-layer X expansion can confirm or enrich seed themes without creating an
  unlimited discovery graph
- Reddit acts as cross-market confirmation and disagreement detection, not as the
  primary signal source
- the runtime outputs a market/theme-level candidate block plus a separate
  direction-to-stock reference map
- the candidate remains advisory and does not directly rewrite the formal
  shortlist or execution tiers

## 2. Phase 1 Boundary

Included:

- a new optional request block:
  - `weekend_market_candidate_input`
- a new derived result block:
  - `weekend_market_candidate`
- a new derived result block:
  - `direction_reference_map`
- X-first weekend synthesis:
  - preferred seed accounts
  - one-layer high-quality theme expansion
- Reddit supplement:
  - cross-market confirmation
  - disagreement / overheating cues
- topic and chain prioritization for Monday watch
- separate leader / high-beta stock reference mapping
- lightweight report surfacing ahead of the formal trade plan

Excluded:

- automatic writing into any formal overlay
- direct promotion into `T1`, `T2`, or formal `T3`
- treating the direction reference map as a formal shortlist
- unrestricted market-wide social graph expansion
- Reddit-first topic generation
- hard dependence on live weekend A-share bars

## 3. Design Principle

Phase 1 adds a **weekend reference layer**, not a new execution layer.

The runtime must distinguish between:

1. `weekend_market_candidate_input`
   - weekend social-source inputs
2. `weekend_market_candidate`
   - synthesized topic / chain candidate output
3. `direction_reference_map`
   - separate leader / high-beta name mapping for each direction
4. formal shortlist outputs
   - the only blocks allowed to represent actual execution readiness

This separation is mandatory. Phase 1 is successful only if weekend information
becomes more useful for Monday preparation without weakening existing shortlist
discipline.

## 4. Input Contract

Phase 1 introduces:

```json
{
  "weekend_market_candidate_input": {
    "x_seed_inputs": [...],
    "x_expansion_inputs": [...],
    "reddit_inputs": [...]
  }
}
```

### 4.1 X Seed Inputs

High-priority operator-selected accounts that act as the primary source of
weekend direction inference.

Preferred fields:

- `handle`
- `url`
- `display_name`
- `tags`
- `theme_aliases`
- `x_index_result_path` or equivalent already-captured source payload
- `quality_hint` (optional)

### 4.2 X Expansion Inputs

One-layer expansion accounts discovered from or curated around the seed set.
They are used to confirm or enrich themes, not to dominate synthesis.

Preferred fields:

- `handle`
- `url`
- `why_included`
- `theme_overlap`
- `quality_hint`
- `x_index_result_path` or equivalent optional payload

### 4.3 Reddit Inputs

Supplemental cross-market discussion used for confirmation, disagreement, and
overheating checks.

Preferred fields:

- `subreddit`
- `thread_url`
- `thread_summary`
- `direction_hint`
- `theme_tags`
- `quality_hint`

## 5. Topic Synthesis Rules

Phase 1 should remain deterministic and conservative.

### 5.1 Seed Priority

Operator-preferred X seeds are the highest-weight source.

A topic can enter the candidate pool when:

- multiple seed accounts converge on the same theme or chain, or
- a high-conviction seed theme is reinforced by the expansion layer

### 5.2 Expansion Accounts

Expansion accounts can:

- confirm that a theme is not isolated to one account
- enrich chain structure
- add overseas or adjacent-market context

Expansion accounts must not, in Phase 1, introduce brand-new primary themes
that are unsupported by the seed layer.

### 5.3 Reddit Role

Reddit is used to:

- confirm cross-market relevance
- surface disagreement
- warn about possible overheating or crowding

Reddit must not dominate topic selection in Phase 1.

### 5.4 Candidate Admission

A topic is eligible for `weekend_market_candidate` only when it satisfies most
of the following:

- supported by multiple preferred X seed accounts, or one strong seed plus
  confirming expansion accounts
- maps to a usable A-share direction or chain
- is not materially contradicted by Reddit discussion
- is specific enough to produce a Monday watch direction

Purely abstract macro narratives with no usable A-share mapping should be
excluded from Phase 1.

## 6. Output Contract

Phase 1 adds two derived result blocks.

### 6.1 `weekend_market_candidate`

```json
{
  "weekend_market_candidate": {
    "candidate_topics": [
      {
        "topic_name": "optical_interconnect",
        "topic_label": "光通信 / 光模块",
        "signal_strength": "high",
        "why_it_matters": "多个高权重 X 种子用户在周末持续强化光通信链条，扩展账户补充上游器件与海外映射，Reddit 侧没有明显反向分歧。",
        "monday_watch": "周一优先看光模块、光器件、上游关键材料的开盘承接与板块联动。"
      }
    ],
    "beneficiary_chains": ["optical_interconnect", "ai_infra"],
    "headwind_chains": [],
    "priority_watch_directions": ["光通信 / 光模块", "AI infra / PCB"],
    "signal_strength": "high",
    "evidence_summary": [
      "Preferred X seeds converged on optical interconnect and AI infra over the weekend.",
      "Expansion accounts reinforced component-chain breadth instead of introducing unrelated themes.",
      "Reddit discussion confirmed overseas AI-infra continuity without strong counter-signals."
    ],
    "x_seed_alignment": "high",
    "reddit_confirmation": "confirming",
    "status": "candidate_only"
  }
}
```

Allowed `status` values:

- `candidate_only`
- `insufficient_signal`

### 6.2 `direction_reference_map`

```json
{
  "direction_reference_map": [
    {
      "direction_key": "optical_interconnect",
      "direction_label": "光通信 / 光模块",
      "leaders": [
        {"ticker": "300308.SZ", "name": "中际旭创"},
        {"ticker": "300502.SZ", "name": "新易盛"}
      ],
      "high_beta_names": [
        {"ticker": "300570.SZ", "name": "太辰光"},
        {"ticker": "688313.SS", "name": "仕佳光子"}
      ],
      "mapping_note": "Direction reference only. Not a formal execution layer."
    }
  ]
}
```

This block is mandatory when candidate topics are present. It must remain
separate from formal shortlist tiers and decision cards.

## 7. Report Placement

The weekend reference layer must appear before the formal trade plan.

Recommended order:

1. `周末主线候选`
2. `周一优先盯的方向`
3. `方向参考映射`
   - 龙头股
   - 弹性股
4. formal trade plan
   - intraday execution cards
   - post-close review cards
   - formal shortlist-derived outputs

The report must make the boundary explicit:

- weekend candidate is a market-prep reference layer
- direction reference mapping is not a formal shortlist

## 8. Interaction With Formal Shortlist

Phase 1 must not automatically:

- write `weekend_market_candidate` into any formal overlay
- promote reference names into formal `T1`, `T2`, or `T3`
- rewrite existing execution decisions

The formal shortlist remains controlled by existing scoring, overlays, and tier
logic.

Phase 2 may later allow accepted weekend candidates to influence formal
observation ranking, but that is explicitly out of scope here.

## 9. Testing Strategy

At minimum, Phase 1 should lock these behaviors:

1. input normalization accepts X seeds, X expansion, and Reddit supplement data
2. topic synthesis favors preferred X seeds and uses expansion accounts only as
   confirmation / enrichment
3. Reddit can confirm or dispute a topic but does not dominate topic generation
4. each admitted topic produces a separate direction reference mapping with
   `leaders`, `high_beta_names`, and a clear `mapping_note`
5. the report places the weekend candidate and direction reference mapping ahead
   of the formal trade plan
6. weekend candidate data does not automatically enter formal execution tiers

## 10. Success Criteria

Phase 1 is successful when:

1. weekend social inputs are compressed into a small set of Monday-relevant
   directions rather than a noisy long list
2. each direction has a usable leader / high-beta reference map
3. formal shortlist discipline remains intact
4. the user can answer, before Monday open:
   - which directions deserve first attention
   - which names to watch inside each direction
   - which names remain reference-only rather than formal execution signals
