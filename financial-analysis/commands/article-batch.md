---
description: Run the automatic article batch workflow across multiple topics or request files
argument-hint: "[batch-request-json]"
---

# Article Batch Command

Use this command when the goal is to automatically build a queue of article
drafts instead of handling one topic at a time.

What it does:

1. reads a batch request with `items[]`
2. runs the article workflow for each item
3. writes per-item staged outputs
4. writes one queue report that shows what is ready for review

Each item can point at:

- an existing indexed result JSON
- an `x-index` request JSON
- a `news-index` request JSON

The batch result gives you:

- one staged folder per topic
- one first-draft article package per topic
- one revision template per topic
- one batch report showing the review queue

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_batch_workflow.cmd "<batch-request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Use this when you want the practical automatic flow:

- several hot-topic inputs
- several first drafts with images where available
- a ready review queue without manually chaining each topic one by one
