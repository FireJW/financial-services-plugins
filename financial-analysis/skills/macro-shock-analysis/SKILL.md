---
name: macro-shock-analysis
description: Framework for analyzing macro shocks such as war, energy spikes, tariffs, sanctions, supply disruptions, inflation shocks, and policy shocks. Use when the task is to judge the nature, size, persistence, transmission, policy reaction, scenario range, and market implications of a macro event. Specialist depth is strongest today for energy and war shocks. Triggers include macro notes, geopolitical shock analysis, inflation spillover work, central-bank reaction-function analysis, scenario trees, and questions like "is this transient or regime-changing?"
---

# Macro Shock Analysis

Use this skill when a macro event may change inflation, growth, policy, or
cross-asset pricing. The order is fixed: define the shock, test whether it
spreads, then judge response and markets.

## Hard Rules

1. Do not jump from a spot price move to a full macro regime change without
   evidence of persistence.
2. Separate first-round effects from second-round effects.
3. Always say what policy can affect and what it cannot.
4. Focus on risks and non-linearity, not only the baseline.
5. Use triggers, invalidation rules, and monitoring signals.
6. Keep market conclusions downstream of shock analysis and policy analysis.
7. Always compare the shock path against a no-further-escalation counterfactual.

## Use This When

- the user wants a macro view on war, energy, shipping, sanctions, tariffs, or
  inflation
- the task is to judge whether a shock is local, persistent, or systemic
- the output needs a policy reaction function instead of a headline summary
- the goal is to turn a fast event into scenarios, watch items, and market maps

Do not use this skill when:

- the task is mainly single-company bottoms-up valuation
- the user only wants a one-paragraph news summary
- there is no real macro transmission question

## Pairing Rule

If the factual layer is still moving, pair this skill with
[autoresearch-info-index](../autoresearch-info-index/SKILL.md) first. Use that
skill to separate confirmed facts from weak signals, then use this skill to
judge transmission, persistence, and response.

## Evidence Gate

If the evidence layer is incomplete, switch to `preliminary mode`.

In preliminary mode:

1. list the unresolved factual questions first
2. avoid fake precision in probabilities and price targets
3. separate `confirmed`, `likely`, and `too early to call`
4. state what new facts would upgrade or downgrade the view

## Read These References As Needed

- For shock types, persistence tests, and propagation paths, read
  [references/shock-framework.md](references/shock-framework.md).
- For monitoring signals, scenario design, and final note structure, read
  [references/monitoring-and-output.md](references/monitoring-and-output.md).
- For war-driven oil and gas analysis, read
  [references/oil-gas-war-shocks.md](references/oil-gas-war-shocks.md).
- For Trump-policy retreat risk, TACO-style pivot probability, and political
  pressure composites, read
  [references/policy-pressure-and-pivot-risk.md](references/policy-pressure-and-pivot-risk.md).
- For repeated war, oil, LNG, and A-share beneficiary mapping tasks, read
  [references/cases/war-energy-chain.md](references/cases/war-energy-chain.md).

## Core Workflow

### 1. Define the shock in one sentence

Write the event as:

- what changed
- when it changed
- which channel it hits first
- why markets care

Bad:

- "The situation is dangerous."

Good:

- "A new oil-supply disruption has lifted crude sharply, raising the risk that a
  relative-price shock becomes broader inflation through transport, power, and
  inflation expectations."

### 2. Classify the shock

Judge the shock on six axes:

1. source
2. size
3. persistence
4. breadth
5. reversibility
6. policy sensitivity

Minimum output:

- `shock_type`
- `initial_channel`
- `estimated_size`
- `expected_duration`
- `contained_or_systemic`

### 3. Map the transmission chain

Always split transmission into layers:

1. direct price effect
2. indirect input-cost pass-through
3. second-round effects via wages, expectations, credit, or FX
4. policy feedback
5. market-pricing feedback

Do not stop at "oil up therefore inflation up." Show the path.

### 4. Judge persistence

The key question is not whether the shock is large today. It is whether it
stays in the system.

Ask:

1. Is this a one-off level shift or a repeating flow shock?
2. Can inventories, rerouting, spare capacity, subsidies, or FX buffers absorb
   it?
3. Are wages, services inflation, or inflation expectations starting to move?
4. Is the shock broadening from one price into many prices?

### 5. Build a risk-first scenario set

Use at least three scenarios:

1. `no-further-escalation / partial fade`
2. `persistent but contained`
3. `broad embedding / regime shift`

For each scenario, include:

- probability range
- what must happen for it to be true
- what would disprove it
- first assets or countries most exposed
- which market move is already priced versus not yet priced
- expected path across `0-72h`, `1-4w`, and `1-3m`

### 6. Write the reaction function

The answer should not be "the central bank will react" in the abstract.

Spell out:

1. what the central bank is likely to look through
2. what would force it to respond
3. what fiscal or regulatory tools may matter more than rates
4. where political constraints change the reaction

Use graduated language. Small short-lived supply shocks can be tolerated.
Broader, more persistent deviations require stronger response.

### 7. Translate into market implications

Only after steps 1-6 are done, map likely impact on:

1. inflation expectations
2. front-end and back-end rates
3. real yields vs breakevens
4. FX, especially commodity importers and exporters
5. commodities
6. equity sectors
7. credit and liquidity stress

Make clear which market view is:

- confirmed by current evidence
- a scenario view
- too early to call

If the shock is energy-linked, do not stop with crude. Separate:

1. global oil
2. seaborne LNG
3. regional gas benchmarks
4. domestic U.S. gas
5. refining / shipping / petrochemical spillovers

Also state which benchmark is the right one for the call. For example:

- Brent before WTI for seaborne oil shock
- JKM-style LNG and TTF before Henry Hub for Qatar / Hormuz LNG shock

## Output Requirements

A good answer should include:

1. one-line shock definition
2. shock classification
3. transmission map
4. persistence judgment
5. scenario matrix
6. reaction function
7. market implications
8. indicator board
9. what to watch next
10. what would change the view
11. horizon split: `0-72h`, `1-4w`, `1-3m`
12. one-line judgment
13. `bias stronger if` and `bias weaker if` conditions

Minimum indicator board:

- spot indicators
- transmission indicators
- policy indicators
- invalidation triggers

Use the fixed output skeleton in
[references/monitoring-and-output.md](references/monitoring-and-output.md)
unless the user asks for a different format.

## Preferred Voice

- precise, not theatrical
- causal, not slogan-driven
- explicit about uncertainty
- clear about what is observed versus inferred

## Default Judgment Standard

If evidence is mixed, prefer:

1. "large but still localized"
2. then test for spillover
3. then upgrade only when second-round or breadth signals confirm it

This skill should slow down overreaction without dulling genuine regime-change
signals.
