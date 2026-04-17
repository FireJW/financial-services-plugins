# Case: Workflow Upgrade With CE And gstack

Use this case when the user wants to improve the research, indexing, drafting,
or publishing workflow itself rather than only analyze one event.

## Division Of Labor

Use gstack for:

- product or workflow framing
- architecture and plan challenge
- browser verification or live UI checking

Use CE for:

- structured implementation planning
- execution against a written plan
- deeper multi-angle review
- compounding the learnings after a real fix or workflow improvement

## Recommended Sequence

1. If the request is still fuzzy, use `plan-ceo-review` or `office-hours` to
   sharpen the problem.
2. Use `plan-eng-review` when the design needs sharper boundaries or execution
   structure.
3. Use `/ce-plan` for the implementation plan that will actually drive the
   change.
4. Use `/ce-work` for the code or workflow implementation.
5. Use `/ce-review` before calling the upgrade complete.
6. Use `/ce-compound` only when the session produced a reusable lesson, not for
   trivial edits.

## Hard Rules

- Keep long-lived source-of-truth logic in the repository, not only in a chat.
- Do not let CE or gstack replace the repository-native finance workflows.
- For finance workflows, keep `news-index`, `x-index`, and macro analysis as
  the truth-building layer.
- Use CE and gstack to improve the workflow around that truth layer, not to
  bypass it.

## Good Targets For This Case

- better retrieval quality
- better source ranking
- stronger review gates before article generation
- cleaner draft feedback memory
- more reliable image capture and preview
- reusable output templates
