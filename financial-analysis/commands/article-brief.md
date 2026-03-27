---
description: Build a structured analysis brief from indexed evidence before article drafting
argument-hint: "[request-json]"
---

# Article Brief Command

Use this command when the user wants a structured middle layer between source
indexing and article drafting, or when they want a macro-safe evidence brief
before writing a market or macro note.

The output lives under `analysis_brief` and should include:

- `canonical_facts`
- `not_proven`
- `open_questions`
- `trend_lines`
- `scenario_matrix`
- `market_or_reader_relevance`
- `story_angles`
- `image_keep_reasons`
- `voice_constraints`
- `macro_note_fields`

Default behavior:

1. load an existing `x-index` or `news-index` result
2. clean and regroup the evidence into a writer-safe brief
3. separate facts, unsupported leaps, and article angles
4. keep the brief reusable for drafting, review, and replay

Macro-native fields are available both as top-level fields inside
`analysis_brief` and grouped again under `analysis_brief.macro_note_fields`.
They now include:

- `one_line_judgment`
- `confidence_markers`
- `current_state_rows`
- `physical_vs_risk_premium`
- `benchmark_map`
- `bias_table`
- `horizon_table`
- `what_changes_the_view`

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_brief.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

The request JSON should point at either a `source_result` object or a
`source_result_path`.
