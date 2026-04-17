# Current Report Problems And Required Improvements

## This is the most important file

If Claude only reads one "what is wrong and what still must change" file, it
should be this one.

## First: what is already fixed locally

Do not assume the report is still at the old stage.

These things are already implemented locally in source/tests:

- trading-profile buckets
- trading-profile subtype
- event-card `交易打法`
- chain-level `链条打法`
- report direction toward compact:
  - `判断: ...`
  - `用法: ...`

So the current problem is not "please invent profile grouping from scratch."

## Problem 1: artifacts are behind source/tests

The biggest handoff risk right now is confusion between:

1. current source/tests
2. stale example artifacts

Source/tests have already moved forward.

The real-X example artifacts are currently stale because rerunning the example
fails with:

- `ValueError: could not convert string to float: '-'`

This is an example regeneration blocker, not evidence that the new reporting
surface failed.

## Problem 2: Event Board still needs stronger editorial compression

Even after the latest local work, the user still wants the surface to read more
like a trader panel than a structured dump.

The desired direction is:

- one strong judgment sentence
- one strong usage sentence

rather than repeating too many profile fields separately.

The repo is already moving in this direction via:

- `trading_profile_judgment`
- `trading_profile_usage`

But Claude should still review whether that compression is strong enough in all
surfaces.

## Problem 3: Chain Map is better, but not finished

`Chain Map` has already moved away from:

- `龙头 / 一线 / 二线`

and toward:

- `稳健核心`
- `高弹性`
- `补涨候选`
- `预期差最大`
- `兑现风险最高`

It also already has `链条打法`.

What is still unfinished:

- same-chain expansion is still incomplete
- same-industry / same-subsector peer coverage is still shallow
- some chains still collapse too many names into `预期差最大`

## Problem 4: `中际旭创` and similar names still expose synthesis pressure

The system already has enough ingredients to say something useful about
`中际旭创`:

- optical chain context
- multiple X/community voices
- `dmjk001` Q1 framing
- pre-result expectation framing
- community reaction patterns

The remaining problem is not missing inputs. It is deciding which few lines
deserve headline status.

Questions the report still needs to foreground more aggressively:

- what the market is actually betting on
- whether this is beat / inline / miss / pricing-a-beat
- which names are stable carriers vs aggressive expressions
- what part is evidence vs expectation
- where the practical trade framing sits right now

## Problem 5: the user-facing output should stay trading-first

The user explicitly prefers trading-attribute grouping over static industry-slot
grouping.

This preference is not optional.

The confirmed direction remains:

- `稳健核心`
- `高弹性`
- `补涨候选`
- `预期差最大`
- `兑现风险最高`

Interpretation:

- old `leaders / peer_tier_1 / peer_tier_2` can still exist internally
- but they should not dominate the user-facing surface
- chain metadata should support the trading view, not replace it

## Required improvement direction now

### A. Do not rebuild the trading-profile layer from scratch

It already exists locally.

### B. Fix the example rerun path first

Before judging the latest output quality from artifacts, make the real-X example
regenerate successfully.

### C. Keep tightening the report into trader language

The highest-value direction remains:

- fewer repeated fields
- stronger editorial emphasis
- faster scanability
- clearer distinction between:
  - stable carrier
  - aggressive expression
  - catch-up
  - expectation-gap
  - sell-the-fact risk

### D. Improve chain / peer expansion quality after artifacts are fresh

Only after the real-X artifact reflects current code should Claude continue with:

- better chain expansion
- better peer coverage
- better separation between `高弹性` and `补涨候选`
- better separation between `预期差最大` and `兑现风险最高`

## Constraint to respect

Do this at the wrapper/orchestration/reporting layer if possible.

Do not assume compiled shortlist core surgery is the first move.
