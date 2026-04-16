# Earnings-Momentum Discovery Lane Design

Date: `2026-04-16`

## Goal

Upgrade the current A-share trading-plan workflow so event-driven winners can
enter the plan from the top of the funnel instead of only appearing as an
after-the-fact explanation layer.

The target state is:

1. keep the current shortlist lane
2. add a second discovery lane driven by earnings / expectation-change events
3. let strong event-driven names reverse-inject into the same final trading
   plan
4. produce outputs that read like a professional trading decision surface, not
   just a filtered shortlist

This is specifically meant to catch cases like:

- annual / quarterly reports with breakout-level numbers
- earnings previews / preannouncements
- big orders
- price hikes
- supply-demand inflections
- rumor + price/volume acceleration + company response combinations
- chain-wide moves such as electronic cloth, compute rental, lithium chain,
  PCB, or AI infra mappings

## User-Confirmed Design Decisions

These points were explicitly confirmed during brainstorming:

1. The chosen architecture is the dual-lane design.
   - Keep the base shortlist lane.
   - Add an `earnings-momentum discovery lane`.
   - Merge the two before final decision output.

2. Discovery lane names may reverse-inject into the main trading plan.
   - They do not need to be preselected by the base shortlist.

3. Trigger logic should require both:
   - expectation-change strength
   - market validation via price/volume/trend behavior

4. Event scope should be broad.
   - not only annual/quarterly results
   - also guidance changes, big orders, price hikes, supply-demand inflections,
     capex, impairment cleanup, policy changes, and similar expectation-moving
     events

5. Rumors are allowed into the workflow.
   - they can enter discovery
   - they should not go directly to `qualified` without stronger confirmation
   - they must carry a confidence range

6. Chain expansion should be upstream/downstream aware.
   - not just “same theme” expansion
   - must reflect where value actually accrues in the chain

7. X is a first-class logic input layer.
   - not truth by itself
   - but useful for thesis framing, chain mapping, and market consensus

## Recommended Architecture

### 1. Base Shortlist Lane

Keep the current `month-end-shortlist` lane as the base technical / liquidity /
risk-reward lane.

Responsibilities:

- broad candidate collection
- exchange / board eligibility
- trend / RS / VCP-style checks
- minimum risk-reward gating
- structured catalyst checks
- shortlist scoring and trade-card generation

This lane remains best at finding technically mature candidates.

### 2. Earnings-Momentum Discovery Lane

Add a new upstream discovery lane that starts from expectation-changing events
instead of from the shortlist universe filter.

Responsibilities:

- detect expectation-changing events
- judge whether the event is strong enough to matter
- check whether the market is already validating the event
- expand the event into upstream/downstream chain candidates
- output event-ranked candidate sets that can merge into the plan

This lane is meant to catch names the base shortlist would otherwise miss.

### 3. Merge Layer

The two lanes merge into a common decision layer.

Merge rules:

- a name may appear from either lane or both
- if both lanes support it, confidence should rise
- if only discovery supports it, the final tier should depend on event quality,
  market validation, and hard-risk checks
- if only shortlist supports it, the name remains eligible even without a fresh
  event story

### 4. Final Decision Layer

The final plan should always output the same three decision buckets:

- `直接可执行`
- `重点观察`
- `链条跟踪`

This structure should replace the current over-reliance on `top_picks` as the
only meaningful surface.

## Discovery Lane Inputs

### A. Formal Event Sources

- annual reports
- quarterly reports
- earnings preannouncements
- earnings flash reports
- earnings revisions
- formal guidance changes
- official company announcements
- order wins
- price hike notices
- capacity launches
- capex changes
- impairment cleanup or one-off reset items

### B. Semi-Formal Sources

- investor relations Q&A
- management commentary
- call summaries
- supplemental decks
- structured media summaries

### C. Rumor / Community / Thesis Sources

- X posts and X threads
- X relayed sell-side / buy-side summaries
- Snowball / Xueqiu posts
- 韭研公社 posts
- community-shared chain maps
- rumor circulation with visible market reaction

### D. Market Validation Sources

- price breakout behavior
- volume expansion
- relative strength acceleration
- chain co-movement
- leader/follower sequencing

## X Platform as a Native Input Layer

Treat X as a structured logic layer, not as a binary “trusted / untrusted”
source.

Use it in three ways:

1. `logic source`
   - personal theses, such as trader/operator logic
2. `chain source`
   - upstream/downstream mapping and value-transfer discussion
3. `institutional summary source`
   - relayed report summaries, desk notes, and crowding narratives

For every X-derived input, assign one of these labels:

- `direct_quote`
- `summary_or_relay`
- `personal_thesis`
- `market_rumor`
- `company_response_reference`
- `official_filing_reference`

This prevents quote-quality inflation while still preserving trading value.

## Rumor Handling Model

Rumors should be allowed into the lane, but handled with two separate scores.

### 1. Confidence Range

Represent rumor credibility as a range, not as true/false.

Suggested bands:

- `20-40`: low
- `40-65`: medium
- `65-80`: medium-high
- `80-90+`: high

Inputs into the range:

- source tier
- multi-source corroboration
- company response quality
- official confirmation or denial
- whether the market is trading it as if it is real

### 2. Trading Usability

Separate from rumor truthfulness.

A rumor can have only medium credibility but still high trading relevance if:

- the stock is breaking out
- volume is strong
- linked names are moving
- the company response is ambiguous instead of a clean denial

Output should show both:

- `rumor_confidence_range`
- `trading_usability`

### 3. Bucket Rule

- rumor-only names may enter `重点观察`
- they may enter `链条跟踪`
- they do not directly enter `直接可执行` unless higher-tier confirmation shows
  up

## Chain Expansion Model

Chain expansion must be value-path based, not just theme-label based.

For each event, classify names into:

1. `事件本体`
2. `直接受益层`
3. `次级受益层`
4. `情绪映射层`

Also classify chain position:

- upstream
- core material
- equipment
- midstream manufacturing
- downstream application
- channel / operator / financing / service layer

Each candidate should state:

- its chain layer
- how value transmits to it
- whether the benefit is direct, second-order, or sentiment-based
- whether it is the most deterministic beneficiary or just a fast follower

This is especially important for cases like:

- PCB / electronic cloth
- lithium chain after CATL-driven moves
- compute rental and linked infra names
- optical / liquid cooling / IDC expansions

## Market Validation and “Funds Enter Early” Logic

The discovery lane should explicitly model the idea that funds often enter
`7-14 days` before the formal report or event.

Use four validation dimensions:

1. `volume anomaly`
   - stronger than recent 5-10 day baseline
   - prefer multi-day accumulation over one-day spikes

2. `price structure breakout`
   - platform breakout
   - box breakout
   - prior-high reclaim
   - key moving-average reclaim

3. `relative strength acceleration`
   - vs index
   - vs sector
   - vs the same chain

4. `chain resonance`
   - multiple linked names moving together
   - leader-first, follower-next sequencing

Final classification:

- `强资金先行`
- `中等资金先行`
- `弱资金先行`

## Final Output Structure

### 1. 直接可执行

For each name include:

- event
- why the event changes earnings power / expectations
- evidence of market validation
- chain role
- why this is the most executable expression
- risk flags
- invalidation

### 2. 重点观察

For each name include:

- event / rumor / response
- confidence range
- trading usability
- current technical posture
- what is still missing before execution
- next watch trigger

### 3. 链条跟踪

For each name include:

- chain layer
- benefit type
- why it is not executable yet
- why it should still remain on the radar

### 4. Event Board

One horizontal surface showing:

- most important expectation-changing events in the last 7-14 days
- confidence
- whether the market has already started trading them
- chain expansion direction

### 5. Chain Map

One horizontal surface showing:

- upstream
- downstream
- equipment
- materials
- operators / service names
- strongest layer
- most deterministic layer
- most crowded layer

## Integration Boundaries

Phase 1 should stay strict on scope:

1. do not modify the compiled shortlist core
2. do not rewrite the existing scoring engine
3. build the discovery lane in wrapper / orchestration layers
4. merge at reporting / decision level first
5. keep `.tmp` outputs unversioned

## Phase 1 Implementation Scope

Phase 1 should include:

1. event-source normalization
2. rumor confidence framework
3. chain expansion by upstream/downstream
4. market-validation classification
5. merge logic into the current plan surface
6. new outputs:
   - `直接可执行`
   - `重点观察`
   - `链条跟踪`
   - `Event Board`
   - `Chain Map`

Phase 1 should not yet require:

- full sell-side earnings reports for every candidate
- universal model refreshes for every name
- complete automated ingestion of every community platform

## Risks and Failure Modes

1. `Noise inflation`
   - too many rumor-driven names
   - mitigated by confidence + usability separation

2. `Theme over-expansion`
   - too many weak chain mappings
   - mitigated by upstream/downstream role tagging and benefit type ranking

3. `Double counting`
   - event score and technical score both implicitly rewarding the same move
   - mitigated by keeping discovery and shortlist evidence visibly separated at
     merge time

4. `Quote quality confusion`
   - X summary mistaken for official disclosure
   - mitigated by source-role labeling

## Testing Strategy

Phase 1 tests should cover:

1. event candidate can enter final decision buckets without base shortlist hit
2. rumor-only case stays out of `直接可执行`
3. official follow-up confirmation can promote a rumor case
4. chain expansion tags upstream/downstream roles correctly
5. event board and chain map render deterministic outputs
6. existing shortlist behavior remains intact when discovery lane is absent

## Recommendation

Implement the dual-lane design in Phase 1 exactly as above.

This gives the workflow a way to catch:

- earnings/expectation-driven breakouts
- early-fund accumulation before reports
- upstream/downstream value-transfer opportunities
- rumor + response + price-action combinations
- X / community / report-summary logic that matters for real trading

without discarding the existing shortlist discipline.
