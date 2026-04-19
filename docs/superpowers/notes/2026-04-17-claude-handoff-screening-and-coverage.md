# Claude Handoff: Screening Mechanism and Plan Coverage

Date: `2026-04-17`
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Branch: `feat/migrate-trading-optimization`

## 1. Why this handoff exists

The immediate next problem is no longer report layout. The current concern is
the **screening mechanism itself**, especially:

- how the shortlist is filtered
- how many names survive into the final trading plan
- whether the final plan is too sparse to be useful in practice

The user feedback is straightforward:

- current trading plans often end up with only about `3` stocks
- that is too few
- the user wants the plan to cover **at least about 10 names**
- the main design question is whether we should change:
  - the upstream filtering logic
  - the presentation/coverage policy
  - or both

This handoff is for planning that next slice.

## 2. Current local state

Current branch:

- `feat/migrate-trading-optimization`

This branch already includes recent local work for:

- dual-mode trading report
- report timestamp stamping
- prior discovery-lane / X-signal integration that was migrated from the older
  history line

This matters because the **display layer has changed**, but the screening
problem is still upstream.

In other words:

- report structure improved
- output quantity did **not** improve enough
- so the next optimization should focus on selection logic and plan coverage

## 3. What is already true today

### 3.1 Report-side top-pick cap is already 10

In `month_end_shortlist_runtime.py`, report/display caps already allow up to 10
top picks:

- `MAX_REPORTED_TOP_PICKS = 10`

Relevant file:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

So the current problem is **not just a display cap**.

### 3.2 The actual bottleneck is upstream scarcity

The practical issue is that upstream screening often produces too few surviving
names:

- too few `top_picks`
- too few `qualified`
- too many names die as:
  - `score_below_keep_threshold`
  - `no_structured_catalyst_within_window`
  - other hard filter failures

### 3.3 There is already a discovery lane

The system already has a discovery/event lane that can ingest:

- official filing / quarterly preview signals
- X-style batch results
- direct X discovery inputs
- rumor / company-response state transitions

This means the codebase is **not missing new-signal ingestion completely**.
However, that discovery lane does not yet reliably solve the "final plan only
has a few names" problem.

## 4. Important files for the next investigation

### Primary runtime

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

This is the main wrapper/orchestration layer. Relevant areas include:

- `MAX_REPORTED_TOP_PICKS = 10`
- filter-profile override handling
- diagnostic scorecard generation
- near-miss and midday status classification
- decision-factor synthesis
- event/discovery lane merge

### Discovery helper

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\earnings_momentum_discovery.py`

Relevant because it influences:

- event card synthesis
- discovery bucket assignment
- trading profile classification
- event state / usability / consensus interpretation

### Reporting tests

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`

### Discovery tests

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_earnings_momentum_discovery.py`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_discovery_merge.py`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_x_style_assisted_shortlist.py`

## 5. Current likely root causes

These are the main hypotheses worth validating.

### Hypothesis A: keep threshold / scoring gates are too restrictive

Many names appear to die as near-misses or just under the keep line. This may
mean:

- thresholds are too strict for the intended trading style
- or the score contributions are not balanced for current market conditions

This is especially relevant when:

- a stock has real event strength
- clear market attention
- but still fails the final shortlist by a narrow score gap

### Hypothesis B: structured catalyst gating is too narrow

The current pipeline still cares heavily about whether there is a sufficiently
structured catalyst within the expected window.

That can be rational, but it may also suppress:

- strong pre-result expectation trades
- chain-driven sympathy names
- early flow-before-confirmation setups

This was already a recurring pain point in prior samples.

### Hypothesis C: discovery lane is informative but not promotive enough

The discovery lane can identify strong names and label them with:

- `qualified`
- `watch`
- `track`

But it may not be feeding that signal back into the **final trading-plan
coverage policy** strongly enough.

Possible symptom:

- discovery says there are multiple relevant names
- final plan still reads as if only a few names matter

### Hypothesis D: plan quantity policy is underspecified

Right now the system has multiple output layers:

- `top_picks`
- `decision_factors`
- `directly_actionable`
- `priority_watchlist`
- `chain_tracking`

There is no explicit, hard product rule saying:

- final plan must surface at least ~10 names overall
- even if only a subset are true "可执行"

So the system may be doing exactly what the code says, but not what the user
actually wants.

## 6. The key product question

Before changing code, this is the main design decision:

### Option 1: Make the true shortlist looser

Meaning:

- more names can become `top_picks` / `qualified`
- actual screening thresholds or gating logic become more permissive

Risk:

- quality dilution
- more mediocre names labeled too strongly

### Option 2: Keep the strict shortlist, but expand final plan coverage

Meaning:

- preserve strict `qualified` logic
- but the final plan always shows something like:
  - a small `可执行` group
  - a larger `继续观察` group
  - chain/relative-value names
- total visible names reaches about 10

Risk:

- may solve presentation but not true screening

### Option 3: Hybrid model

Meaning:

- slightly relax or rebalance upstream filtering
- and also define a hard output policy for total plan coverage

This is likely the most realistic direction.

## 7. My current recommendation for the next design pass

I would recommend Claude investigate a **hybrid design**.

Concretely, plan around these principles:

1. Do **not** force 10 names into `可执行`
   - that would likely degrade quality

2. Do require the final plan to cover about 10 names overall
   - for example across:
     - `可执行`
     - `继续观察`
     - chain-sympathy / expansion names

3. Revisit how near-miss names are promoted
   - especially event-backed names that narrowly miss the keep line

4. Revisit how discovery-lane names feed into the final plan
   - not just into report appendices
   - but into the actual "what we care about today" list

5. Decide explicitly whether the final plan should be:
   - score-first
   - event-first
   - or blended

## 8. What Claude should produce next

The next useful output is **not code first**.

Claude should first produce a design/spec that answers:

1. What is the target final plan size?
   - exactly 10?
   - up to 10?
   - minimum 10 if enough names exist?

2. How should names be grouped?
   - `可执行`
   - `继续观察`
   - `链条跟踪`
   - or a new structure

3. Which upstream gates are allowed to change?
   - keep threshold
   - catalyst gating
   - discovery promotion
   - scoring weights

4. What should remain unchanged?
   - compiled shortlist core?
   - raw scoring logic?
   - wrapper only?

5. How do we test success?
   - not only unit tests
   - but also realistic plan-coverage smoke tests

## 9. Constraints and non-goals

Unless explicitly decided otherwise, Claude should assume:

- compiled shortlist core should remain untouched if possible
- prefer wrapper/orchestration changes first
- do not destroy the improved report structure
- do not regress current discovery/event ingestion
- do not solve this by padding with low-value names that have no decision use

## 10. Suggested starting point for Claude

Ask Claude to start from this question:

> "Design how the shortlist and discovery pipeline should produce a final
> trading plan that usually covers around 10 names without diluting true
> execution-quality signals. Be explicit about which names are allowed to enter
> through score, which through event/discovery, and how final coverage should be
> balanced across execution and watchlist tiers."

That should lead Claude toward the right planning problem instead of only
changing presentation caps.
