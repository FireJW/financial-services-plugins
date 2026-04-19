# Trading Profile Surface Design

Date: `2026-04-16`

## Goal

Upgrade the current discovery report so the main user-facing grouping reflects
trading profile rather than static industry rank.

The key shift is:

- stop treating `龙头 / 一线 / 二线` as the main surface
- start treating
  - `稳健核心`
  - `高弹性`
  - `补涨候选`
  - `预期差最大`
  - `兑现风险最高`
  as the main decision-oriented grouping

## Why this change is needed

The current report already has enough structured information, but it is still
too close to a diagnostic dump.

The user explicitly said the current chain-tier framing is less useful than a
trading-attribute framing. The system should therefore optimize for how a trader
would use the output, not for static industry hierarchy.

## Scope

This design is intentionally narrow:

- wrapper/reporting only
- no compiled shortlist core changes
- no new external ingestion dependencies
- no attempt to solve full chain-coverage quality in this slice

## Proposed design

### 1. Add a trading-profile classifier

Each synthesized event card should receive:

- `trading_profile_bucket`
- `trading_profile_reason`

The classifier should use existing fields where possible:

- `event_state`
- `trading_usability`
- `expectation_verdict`
- `community_conviction`
- `priority_score`
- `chain_role`
- `benefit_type`
- `leaders / peer_tier_1 / peer_tier_2`

### 2. Keep old peer/leader data as internal support

`leaders / peer_tier_1 / peer_tier_2` can remain useful as inputs, but they
should no longer dominate the user-facing report structure.

### 3. Rework the report surfaces

`Chain Map` should keep chain anchors, but under each chain it should render the
new trading-profile buckets instead of `龙头 / 一线 / 二线`.

`Event Board` and `Event Cards` should explicitly show:

- `交易属性分层`
- `分层依据`

This keeps the report judgment-first without discarding the richer evidence that
already exists.

## Success criteria

1. Report no longer relies on `一线 / 二线` as the main presentation
2. Event cards expose a concrete trading-profile bucket
3. Chain map renders the five new buckets
4. Existing discovery/event-card behavior still works

## Non-goals

- perfect industrial-chain expansion
- consensus-grade beat/miss accounting
- full redesign of all report sections

This slice is about upgrading the main decision surface first.
