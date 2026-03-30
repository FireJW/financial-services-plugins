# Case: Workflow Improvement Loop

## Use When

- the user wants Codex to get better at a recurring task over time
- examples include stock analysis templates, code-fix flow, and document cleanup
- the goal is not just one answer, but a repeatable improvement loop

## Native Route

1. Use [`autoresearch-loop`](../../autoresearch-loop/SKILL.md) as the outer loop
2. If the workflow change itself needs sharper framing or a stronger build
   sequence, pair it with gstack plus CE:
   - frame and challenge with `plan-ceo-review` and `plan-eng-review`
   - implement with `/ce-plan`, `/ce-work`, `/ce-review`
   - keep `/ce-compound` for sessions that produce a reusable lesson
3. Pick the matching task layer:
   - stock or news indexing -> [`autoresearch-info-index`](../../autoresearch-info-index/SKILL.md)
   - code repair -> [`autoresearch-code-fix`](../../autoresearch-code-fix/SKILL.md)
   - document cleanup -> `autoresearch-loop` with the `doc-workflow` profile
4. Define a sample pool, scorecard, and rollback rule before trying to improve

## Required Output Shape

- fixed task profile
- sample set
- current baseline
- score dimensions
- candidate change
- verification result
- keep / rollback decision

## Anti-Patterns

- do not optimize a workflow before a stable sample set exists
- do not keep a change just because it sounds better
- do not mix different task types into one loop
- do not let CE or gstack replace the repository-native finance workflows that
  actually produce the evidence or analysis
