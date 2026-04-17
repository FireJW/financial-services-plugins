---
description: Automatically rank candidate topics and send the top ones into the article batch workflow
argument-hint: "[auto-queue-request-json]"
---

# Article Auto Queue Command

Use this command when you have a pool of candidate topics or request files and
want the system to decide which ones should be drafted first.

What it does:

1. loads candidate inputs
2. builds or reads their indexed source results
3. scores them by article readiness
4. keeps the top `N`
5. pushes those top items into the article batch workflow

This gives you:

- a ranked candidate list
- staged indexed source files
- a batch article queue for the selected items
- a review-ready output folder for the winners
- per-selected-candidate `final_publication_readiness` /
  `final_manual_review_*` fields for compatibility
- the same `workflow_publication_gate` object on ranked candidates so downstream
  automation can read one shared publication gate

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_auto_queue.cmd "<auto-queue-request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Use this when you want the next automation step after batch generation:

- many possible hot topics
- automatic ranking
- only the best few turned into draft articles and revision templates
