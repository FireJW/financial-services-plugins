---
description: Build an evidence pack from X posts and bridge it into news-index
argument-hint: "[request-json]"
---

# X Index Command

Use this command when the user wants to collect X posts as source-traceable
evidence before analysis or article writing.

The output should prioritize:

- direct main-post text extraction
- same-author thread text when available
- image OCR as supplemental evidence only
- screenshots and source links for review

Default behavior:

1. discover candidate X post URLs from manual URLs, keywords, or allowlisted accounts
2. fetch each post and try to read visible post text before any OCR fallback
3. save the root-post screenshot plus media artifacts when available
4. build `post_summary`, `media_summary`, and `combined_summary`
5. bridge the kept posts into `news-index` as `social` observations

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_x_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

For the local helper path, pass an `x-index` request JSON file. The helper
prints JSON to stdout by default and writes the human-readable Markdown report
only when `--markdown-output` is provided.
