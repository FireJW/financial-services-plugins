---
description: Revise an existing article draft while preserving citations and image attachments
argument-hint: "[request-json]"
---

# Article Revise Command

Use this command when the user has already reviewed an article package and wants
Codex to rebuild it without dropping source links or images. The revise step now
also runs a red-team challenge and produces a rewritten final draft.

The output should preserve:

- the citation list
- the selected images unless explicitly changed
- revision history
- the article-ready markdown with image embeds
- a `review_rewrite_package`
- a `quality_gate`

Default behavior:

1. load an existing article draft result
2. apply revision notes or a manual body override
3. red-team the draft for unsupported leaps and overclaiming
4. rebuild the article package in a safer form
5. append a revision-history entry

Useful revision inputs:

- `feedback.summary`
  - plain-language review notes
- `feedback.tone`
  - e.g. `cautious`, `direct`
- `feedback.drop_image_asset_ids[]`
  - remove specific images from the article package
- `feedback.keep_image_asset_ids[]`
  - keep or pin only the requested images near the front
- `edited_body_markdown`
  - replace the body while keeping citations, image assets, and revision history attached

This command is designed for the review loop:

- first generate an image-aware article package
- then revise it without losing the saved screenshots, media, or source links
- keep stacking revision history so later workflow tuning has concrete feedback to learn from

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_revise.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>] [--draft-mode balanced|image_first|image_only]`

The request JSON should point at either an `article_result` object or an
`article_result_path`.

Useful request fields:

- `pinned_image_ids[]` or `feedback.keep_image_asset_ids[]` to keep specific images at the front
- `drop_image_ids[]` or `feedback.drop_image_asset_ids[]` to remove specific images
- `draft_mode=image_only` to keep the article minimal and image-led
