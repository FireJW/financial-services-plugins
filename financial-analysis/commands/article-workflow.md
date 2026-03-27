---
description: Run the end-to-end article workflow from indexed evidence or a fresh index request
argument-hint: "[request-json]"
---

# Article Workflow Command

Use this command when the user wants one runnable flow that:

1. takes an existing `x-index` or `news-index` result, or a fresh index request
2. builds a structured analysis brief from that evidence
3. builds the first article draft with images attached
4. runs a red-team challenge plus automatic rewrite pass
5. prepares the next revision template so the review loop can continue without re-grabbing the same inputs
6. writes `ARTICLE-FEEDBACK.md` so the next edit pass can happen in markdown instead of JSON

The workflow writes staged outputs for:

- the source result
- the source report
- the analysis brief result
- the analysis brief report
- the article draft result
- the article draft report
- the article review result
- the article review report
- the final article result
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

- hot topic -> fact-checked brief
- brief -> first draft with images
- draft -> red-team challenge -> rewritten draft
- your review notes -> revision template
- revised draft without re-indexing the same source package
