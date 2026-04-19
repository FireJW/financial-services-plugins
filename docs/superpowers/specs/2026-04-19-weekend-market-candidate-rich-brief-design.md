# Weekend Market Candidate Rich Brief Design

**Date:** 2026-04-19  
**Status:** Approved design  
**Scope:** `weekend_market_candidate` contract and markdown rendering only

## 1. Goal

Upgrade the Phase 1 `weekend_market_candidate` output from a light topic summary
into a richer Monday-prep brief that explains:

- why one direction ranks above another
- which inputs drove that ranking
- which sources matter most

The new behavior should still preserve the existing boundary:

- this remains a reference layer
- it does not become a formal execution layer
- it does not auto-promote names into shortlist tiers

## 2. Problem Statement

The current output contract is too light for ranking transparency.

Today, `weekend_market_candidate` can tell the user:

- what the top topic is
- why it matters
- what to watch on Monday

But it cannot explicitly tell the user:

- why this direction is first priority rather than second
- how strong the seed-account consensus was
- whether Reddit support was confirming or weak
- which 1-3 sources actually drove the ranking

As a result, the markdown brief reads like a conclusion without enough
decision-path visibility.

## 3. Design Principle

The richer brief must be a **contract upgrade**, not a markdown-only embellishment.

This means:

- JSON becomes the source of truth
- markdown simply renders richer structured fields
- older fields remain in place for compatibility

The richer brief is successful only if the user can understand ranking logic
without reading a long narrative report.

## 4. Contract Upgrade

The existing `weekend_market_candidate.candidate_topics[*]` structure keeps all
current fields and adds four new fields:

- `priority_rank`
- `ranking_logic`
- `ranking_reason`
- `key_sources`

### 4.1 Existing Fields Retained

- `topic_name`
- `topic_label`
- `signal_strength`
- `why_it_matters`
- `monday_watch`

### 4.2 New Field: `priority_rank`

Defines display order and ranking position.

Allowed values in Phase 1:

- positive integer, starting from `1`

Example:

```json
"priority_rank": 1
```

### 4.3 New Field: `ranking_logic`

Structured ranking dimensions for scan-friendly comparison.

Phase 1 fields:

- `seed_alignment`
- `expansion_confirmation`
- `reddit_confirmation`
- `noise_or_disagreement`

Allowed values:

- `high`
- `medium`
- `low`

Example:

```json
"ranking_logic": {
  "seed_alignment": "high",
  "expansion_confirmation": "high",
  "reddit_confirmation": "high",
  "noise_or_disagreement": "low"
}
```

### 4.4 New Field: `ranking_reason`

A short explanation that directly answers:

- why this direction is ranked here
- why it is ahead of lower-priority directions

Example:

```json
"ranking_reason": "Preferred X seeds and expansion accounts aligned cleanly on optical interconnect, Reddit confirmed the same direction, and disagreement stayed limited, so this direction ranks first for Monday watch."
```

### 4.5 New Field: `key_sources`

A short list of the most important ranking-driving sources.

Phase 1 should usually keep:

- `1-3` entries per topic

Preferred source mix:

- one seed source
- one expansion confirmation source
- one Reddit confirmation source

This is a preference, not a hard requirement.

Each entry includes:

- `source_name`
- `source_kind`
- `url`
- `summary`

Allowed `source_kind` values in Phase 1:

- `x_seed`
- `x_expansion`
- `reddit_confirmation`

Example:

```json
"key_sources": [
  {
    "source_name": "aleabitoreddit",
    "source_kind": "x_seed",
    "url": "https://x.com/aleabitoreddit",
    "summary": "Continued to frame photonics and optical interconnect as an AI infrastructure bottleneck."
  },
  {
    "source_name": "stockedgeN",
    "source_kind": "x_expansion",
    "url": "https://x.com/stockedgeN/status/2043796885735956990",
    "summary": "Reinforced silicon-photonics and connectivity-stack follow-through with concrete company references."
  },
  {
    "source_name": "r/stocks",
    "source_kind": "reddit_confirmation",
    "url": "https://www.reddit.com/r/stocks/comments/1spdqcl/photonics_and_optics_related_stocks/",
    "summary": "Weekend cross-market discussion kept photonics in focus as a next-stage AI bottleneck."
  }
]
```

## 5. Ranking Logic Interpretation

Phase 1 uses four ranking dimensions.

### 5.1 `seed_alignment`

Measures whether preferred X seed accounts converge on the same topic.

- `high`
  - multiple preferred seeds align clearly, or one very strong seed provides a
    high-conviction centered signal
- `medium`
  - partial seed support exists, but alignment is weaker
- `low`
  - seed support is sparse or unclear

### 5.2 `expansion_confirmation`

Measures whether one-layer expansion accounts reinforce the same topic.

- `high`
  - multiple expansion accounts confirm the same direction
- `medium`
  - some confirmation exists, but coverage is limited
- `low`
  - little or no meaningful expansion support

### 5.3 `reddit_confirmation`

Measures whether Reddit provides cross-market validation.

- `high`
  - multiple useful Reddit signals reinforce the same direction
- `medium`
  - partial Reddit confirmation exists
- `low`
  - weak or absent Reddit support

### 5.4 `noise_or_disagreement`

Measures how noisy, disputed, or headline-sensitive the theme is.

- `low`
  - direction is comparatively clean and coherent
- `medium`
  - some disagreement or crowding is present
- `high`
  - material disagreement, crowding, or headline reversal sensitivity exists

This field is a ranking drag rather than a positive signal.

## 6. Markdown Rendering Upgrade

The richer markdown brief should render each ranked direction as a short
structured card instead of a long paragraph.

Recommended structure per direction:

1. direction header
2. ranking logic
3. ranking reason
4. key sources
5. direction reference map

Example shape:

```md
## 第一优先方向：光通信 / 光互联

### 排序逻辑
- 种子共振：高
- 扩展确认：高
- Reddit 验证：高
- 分歧 / 噪音：低

### 为什么排第一
Preferred X seeds and expansion accounts aligned most cleanly here, Reddit
validated the same direction, and disagreement remained limited.

### 最关键 source
- `@aleabitoreddit`
  - 链接：...
  - 摘要：...
- `stockedgeN`
  - 链接：...
  - 摘要：...
- `r/stocks`
  - 链接：...
  - 摘要：...

### 方向参考映射
- 龙头股：中际旭创、新易盛
- 弹性股：太辰光、仕佳光子
```

## 7. Backward Compatibility

Backward compatibility rules are strict:

1. existing fields remain present
2. new fields are additive
3. markdown must continue to render if new fields are missing
4. missing richer fields should fall back to the older brief style rather than
   fail rendering

This allows the richer brief to be adopted incrementally.

## 8. Out of Scope

Still excluded in this design:

- automatic overlay creation from the richer brief
- direct shortlist ranking changes
- formal execution-tier mutation
- source authority scoring beyond the simple source-role structure
- history-based source win-rate modeling

## 9. Testing Strategy

At minimum, Phase 1.5 should lock:

1. each topic can carry `priority_rank`, `ranking_logic`, `ranking_reason`, and
   `key_sources`
2. `ranking_logic` values stay within `high / medium / low`
3. `key_sources` carry `source_name`, `source_kind`, `url`, and `summary`
4. markdown renders the richer structure when those fields exist
5. markdown still falls back safely when those fields do not exist
6. richer brief fields do not alter formal shortlist tiers

## 10. Success Criteria

The richer brief upgrade is successful when:

1. first-priority versus second-priority directions are explicitly explainable
2. the user can see the decisive ranking logic at a glance
3. the user can see the most important supporting sources without reading a long
   narrative
4. the report remains concise and scan-friendly
5. the richer brief still behaves as a reference layer rather than an execution
   layer
