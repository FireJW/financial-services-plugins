---
description: Run the end-to-end article workflow from indexed evidence or a fresh index request
argument-hint: "[request-json]"
---

# Article Workflow Command

Use this command when the user wants one runnable flow that:

1. takes an existing `x-index` or `news-index` result, or a fresh index request
2. builds the first article draft with images attached
3. prepares the next revision template so the review loop can continue without re-grabbing the same inputs

The workflow writes staged outputs for:

- the source result
- the source report
- the article draft result
- the article draft report
- the article revision template
- the workflow summary report

Accepted inputs:

- an existing indexed result JSON
- an `x-index` request JSON
- a `news-index` request JSON

Useful modes:

- `draft_mode=balanced`
  - normal article draft
- `draft_mode=image_first`
  - visual-first draft with lighter text
- `draft_mode=image_only`
  - minimal text, mainly for understanding and keeping the images

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_workflow.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>] [--draft-mode balanced|image_first|image_only]`

Use this when you want the practical loop:

- hot topic -> first draft with images
- your review notes -> revision template
- revised draft without re-indexing the same source package
