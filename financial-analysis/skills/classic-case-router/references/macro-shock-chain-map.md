# Case: Macro Shock Chain Map

## Use When

- the user asks which stocks benefit or suffer from war, oil, gas, shipping,
  tariff, sanction, export-control, or policy shocks
- the user wants A-share, Hong Kong, or U.S. equity mapping from a macro event
- the user asks for transmission logic, not just a theme list

## Native Route

1. Verify the live event tape through
   [`autoresearch-info-index`](../../autoresearch-info-index/SKILL.md)
2. Run [`macro-shock-analysis`](../../macro-shock-analysis/SKILL.md)
3. If multiple stocks or sectors are involved, continue into
   [`idea-generation`](../../../equity-research/skills/idea-generation/SKILL.md)
4. If valuation or target price logic is requested, extend into sector, comps,
   or model-update workflows

## Required Output Shape

- fact board
- company classification table
- transmission chain
- benefit vs damage verdict
- horizon split
- scenario price map when the user asks for target price, month-end price, or trading plan
- invalidation triggers

When `scenario price map` is required, include:

- optimistic path
- base path
- pessimistic path
- upgrade triggers
- downgrade triggers
- invalidation condition

## Anti-Patterns

- do not write `oil up therefore all energy stocks benefit`
- do not skip chain position classification
- do not treat price action as proof of earnings transmission
