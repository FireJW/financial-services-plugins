# Task Profiles

This file defines the first four task profiles supported by the autoresearch
loop.

## `code-fix`

Companion skill:

- [../../autoresearch-code-fix/SKILL.md](../../autoresearch-code-fix/SKILL.md)

### Goal

Improve repeatable bug-fix workflows so they become:

- more reproducible
- more targeted
- less regression-prone
- easier to verify

### Hard checks

- the issue is reproducible before the fix
- the fix can be verified after the change
- no new critical failure is introduced
- the solution matches the root cause instead of suppressing symptoms

### Suggested score dimensions

- root-cause quality
- fix minimality
- validation coverage
- regression risk control
- debugging efficiency
- reuse value of the final notes

### Stop conditions

- bug is no longer reproducible
- relevant checks pass consistently
- last two iterations add no meaningful verification improvement

## `doc-workflow`

### Goal

Improve document cleanup or restructuring so the result becomes:

- clearer
- less repetitive
- more consistent
- easier for the target reader to use

### Hard checks

- key information is preserved
- required sections remain present
- terminology and versions stay consistent
- no major contradiction is introduced

### Suggested score dimensions

- structure clarity
- information fidelity
- duplication reduction
- consistency
- usability
- maintainability

### Stop conditions

- all hard checks pass
- score gains flatten for three rounds
- reader walkthrough passes on the target sample

## `stock-template`

### Goal

Improve recurring stock analysis output so the template becomes:

- more complete
- more traceable
- more stable in structure
- safer in time-sensitive factual handling

### Hard checks

- all current or latest references use absolute dates
- key facts are traceable to sources
- required sections are present
- valuation method matches the company and period
- fact and judgment are clearly separated

### Suggested score dimensions

- information completeness
- factual accuracy
- logic coherence
- valuation comparability
- risk coverage
- readability and template stability

### Stop conditions

- the recent sample set reaches the target threshold
- no new hard-fail issue is found
- gains flatten across several rounds

## `info-index`

### Goal

Improve recurring information-indexing output so the workflow becomes:

- more source-traceable
- more explicit about uncertainty
- better anchored in absolute time
- more reusable for later retrieval and decision-making
- better at putting fresh, high-value evidence above stale background context

### Hard checks

- all time-sensitive references use absolute dates
- key claims are traceable to specific sources
- confirmed facts and judgment are clearly separated
- contradictory or missing confirmations are disclosed
- source recency is checked before conclusions are written

### Suggested score dimensions

- source coverage
- claim traceability
- recency discipline
- contradiction handling
- signal extraction
- retrieval efficiency
- freshness capture
- shadow-signal discipline
- source-promotion discipline
- blocked-source handling

### Stop conditions

- the recent sample set reaches the target threshold
- no new hard-fail issue is found
- gains flatten across several rounds

## Ordering Rule

Default rollout order:

1. `code-fix`
2. `doc-workflow`
3. `stock-template`
4. `info-index`

This order should be preserved unless there is a concrete reason to change it.
