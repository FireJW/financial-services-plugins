---
description: Build a structured analysis brief from indexed evidence before article drafting
argument-hint: "[request-json]"
---

# Article Brief Command

Use this command when the user wants a structured middle layer between source
indexing and article drafting.

The output should include:

- `canonical_facts`
- `not_proven`
- `open_questions`
- `trend_lines`
- `scenario_matrix`
- `market_or_reader_relevance`
- `story_angles`
- `image_keep_reasons`
- `voice_constraints`

Default behavior:

1. load an existing `x-index` or `news-index` result
2. clean and regroup the evidence into a writer-safe brief
3. separate facts, unsupported leaps, and article angles
4. keep the brief reusable for drafting, review, and replay

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_brief.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

The request JSON should point at either a `source_result` object or a
`source_result_path`.
