# Claude Handoff: A-Share Trading Plan And Discovery System

Date: `2026-04-17`
Timezone: `Asia/Shanghai`
Prepared for: Claude / cross-agent handoff

## 1. What This System Is Trying To Do

This repo is building a practical A-share trading decision surface with two
lanes:

1. a structured shortlist / trading-plan lane for technically mature names
2. a more aggressive discovery lane so we do not miss names driven by earnings,
   orders, price hikes, supply-demand changes, rumors, company responses, and
   X/community logic

The user cares much more about:

- expectation trading than backward-looking report decomposition
- market reaction and consensus formation than perfect data cleanliness
- practical decision usefulness than raw field completeness

In plain terms, the system should answer:

- what is actionable now
- why now
- what is the market already pricing
- what still looks underpriced
- where sell-the-fact /兑现 risk is highest

## 2. Canonical Repo / Branch / Safety Context

Canonical worktree:

- `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup`

Branch:

- `feat/codex-plan-followup`

Latest synced / pushed commit:

- `0dc071f feat: strengthen discovery event cards`

Important nuance:

- the branch has moved materially forward locally after `0dc071f`
- current source/tests contain additional uncommitted discovery/reporting work
- Claude should treat local source as newer than the last pushed commit

Surrounding safety context:

- `D:\Users\rickylu\dev\financial-services-stock` is a snapshot/export path, not
  the canonical git target
- `D:\Users\rickylu\dev\financial-services-plugins` has a damaged `.git` and is
  treated as read-only
- active development should continue only in
  `financial-services-plugins-clean`

## 3. Read These First

If context is tight, read in this order:

1. `docs/superpowers/notes/claude-handoff/2026-04-16-00-index.md`
2. `docs/superpowers/notes/claude-handoff/2026-04-16-01-system-overview-and-product-goal.md`
3. `docs/superpowers/notes/claude-handoff/2026-04-16-04-current-report-problems-and-required-improvements.md`
4. `docs/superpowers/notes/claude-handoff/2026-04-16-02-runtime-architecture-and-code-map.md`
5. `docs/superpowers/notes/claude-handoff/2026-04-16-03-x-discovery-and-real-signal-fixtures.md`
6. `docs/superpowers/notes/claude-handoff/2026-04-16-05-next-implementation-slice-for-claude.md`

If you only inspect code before changing anything, inspect:

1. `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
2. `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`
3. `tests/test_month_end_shortlist_degraded_reporting.py`
4. `tests/test_earnings_momentum_discovery.py`

## 4. Current Runtime Architecture

### 4.1 Base shortlist wrapper lane

Primary file:

- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

Responsibilities:

- normalize request payloads
- preserve wrapper-level profile overrides
- merge X/discovery inputs
- call the compiled shortlist runtime
- enrich results for report output

The compiled shortlist core still lives behind `.pyc` artifacts in
`short-horizon-shortlist`, so wrapper-level enhancements remain the main safe
extension point.

### 4.2 Discovery helper

Primary file:

- `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`

Responsibilities:

- discovery-candidate normalization
- rumor confidence
- market validation
- event state
- trading usability
- discovery bucket assignment
- auto-derived discovery candidates
- X-style candidate extraction
- multi-source event-card synthesis
- trading-profile classification and summarization

### 4.3 Event cards

The system no longer renders only flat discovery rows. It now merges multiple
signals for the same ticker into one event card.

Sources merged into a card can include:

- official filing / preview / company event
- X summary / X thread / relay summary
- rumor / company response
- market validation

### 4.4 Trading-profile surface

This is already implemented locally in source and tests.

Current top-level buckets:

- `稳健核心`
- `高弹性`
- `补涨候选`
- `预期差最大`
- `兑现风险最高`

Current supporting fields on event cards:

- `trading_profile_bucket`
- `trading_profile_subtype`
- `trading_profile_reason`
- `trading_profile_playbook`
- `trading_profile_judgment`
- `trading_profile_usage`

Meaning:

- `bucket` is the primary trading identity
- `subtype` gives a more precise trading flavor
- `judgment` compresses bucket + subtype + reason into one sentence
- `usage` compresses playbook into one action-oriented sentence

### 4.5 Chain-level surface

`Chain Map` is no longer just static peer listing.

It already supports:

- chain anchors
- bucketed names per chain
- `链条打法`

That chain playbook is generated from the mix of profiles present inside each
chain.

## 5. Current Output Surfaces

The wrapper can already render:

- `## 午盘/盘后操作建议摘要`
- `## Decision Factors`
- `## 直接可执行`
- `## 重点观察`
- `## 链条跟踪`
- `## Event Board`
- `## Chain Map`
- `## Event Cards`

Current local source intent for `Event Board / Event Cards`:

- keep `阶段`
- keep `预期判断`
- replace the old repeated profile lines with:
  - `判断: ...`
  - `用法: ...`

## 6. Current X / Community Integration Status

X is a first-class logic input layer now.

The system supports:

- direct X-derived discovery candidates
- batch-style X ingestion
- inline `x_discovery_request`
- file-based `x_discovery_request_path`
- batch-style request payloads with `subject_registry`
- chain inference from `logic_basket_rules`
- rumor -> response -> confirmation / denial handling

Real fixture/example inputs currently include:

- `twikejin`
- `LinQingV`
- `tuolaji2024`
- `dmjk001`

Relevant fixture/example files:

- `tests/fixtures/x_discovery_real/multi-source-batch.request.json`
- `financial-analysis/skills/month-end-shortlist/examples/x-discovery-real-multi-source-batch.template.json`

Important real post already integrated:

- `https://x.com/dmjk001/status/2044774708391125067`

Used for `中际旭创` Q1 expectation framing around:

- `800G`
- `1.6T`
- Q1 volume ramp
- gross margin stable improvement

## 7. Current Local-Only Progress Beyond `0dc071f`

These changes exist in the current local worktree and are already covered by
tests, but are not yet committed:

1. trading-profile buckets moved from design target to real runtime output
2. trading-profile subtypes added
3. event-card `交易打法` added
4. chain-level `链条打法` added
5. `Event Board / Event Cards` compressed from four repeated profile lines into
   two shorter lines:
   - `判断: ...`
   - `用法: ...`

Most relevant modified files:

- `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`
- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`

## 8. What Is Already Verified

Current fresh verification on the local tree:

- focused discovery/reporting regression:
  `47 passed`

Relevant regression slice:

- `tests/test_x_style_assisted_shortlist.py`
- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_discovery_merge.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`

## 9. What Is Still Wrong

The problem is no longer "missing fields." The problem is product quality of the
decision surface.

Still wrong:

1. some output areas are still more structured than editorial
2. chain expansion and same-industry peer expansion are still incomplete
3. some names still fall into `预期差最大` too easily
4. the real-X example artifacts are currently stale relative to source/tests

The most important nuance:

- source/tests have advanced
- example artifacts have not
- do not confuse artifact lag with source-level regressions

## 10. Current Real Blocker

The main blocker right now is not the trading-profile logic itself.

The blocker is that rerunning the real-X example currently crashes before
writing fresh output.

Current failure:

- `ValueError: could not convert string to float: '-'`

Observed path:

- user-facing wrapper script calls into the compiled shortlist runtime
- the compiled path reaches `build_candidate_from_universe`
- one stale/sample request value is still being parsed as a float and fails on
  `'-'`

Implication:

- `.tmp/real-x-event-card-example/report.md`
- `.tmp/real-x-event-card-example/result.json`

are currently stale and should not be treated as the definitive representation
of the latest local code.

## 11. Recommended Next Work For Claude

Do **not** restart the reporting redesign from zero.

Assume the local branch already contains the correct direction and keep building
from current source.

Recommended order:

1. inspect the current local diff in:
   - `earnings_momentum_discovery.py`
   - `month_end_shortlist_runtime.py`
   - `test_earnings_momentum_discovery.py`
   - `test_month_end_shortlist_degraded_reporting.py`
2. preserve the current trading-profile surface
3. fix the real-X example rerun path so artifacts can be regenerated
4. regenerate:
   - `.tmp/real-x-event-card-example/report.md`
   - `.tmp/real-x-event-card-example/result.json`
5. only after artifact regeneration, continue polishing:
   - event-board brevity
   - chain expansion quality
   - same-industry / peer grouping quality

## 12. What Claude Should Not Waste Time Rebuilding

These are already in place locally:

- trading-profile buckets
- trading-profile subtype
- event-card playbook
- chain playbook
- `判断 / 用法` rendering path in report code

So the next work is not:

- "invent trading-profile grouping from scratch"
- "switch from 龙头/一线/二线 to buckets for the first time"

That work is already done locally.

The next useful work is:

- make the example path and artifacts catch up
- keep improving synthesis quality on top of the current local surface
