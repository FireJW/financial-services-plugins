---
description: Build a reviewable article draft with images and citations from an indexed evidence result
argument-hint: "[request-json]"
---

# Article Draft Command

Use this command when the user wants a first article package built from an
existing `x-index` or `news-index` result.

The output should include:

- a draft title and subtitle
- a body draft that stays source-traceable
- selected key images or screenshots
- an article-ready markdown version with those images embedded
- a citation list
- editor notes when the evidence is weak or screenshot-only

Default behavior:

1. load an existing indexed evidence result
2. choose the most useful images and screenshots
3. generate a reviewable article draft
4. keep the citation list and image package attached

Useful modes:

- `draft_mode=balanced`
  - normal article draft with text, citations, and images
- `draft_mode=image_first`
  - visual-first draft with lighter text and the key images pushed higher
- `draft_mode=image_only`
  - minimum text, maximum visual evidence; use this when the goal is mainly to understand what the images show and keep those images ready for the article

Useful image strategies:

- `image_strategy=mixed`
  - keep the strongest mix of screenshots and media images
- `image_strategy=prefer_images`
  - bias toward post media when it contains the useful chart or screenshot
- `image_strategy=screenshots_only`
  - keep only screenshots or saved visual evidence, useful when the page is blocked or text extraction is weak

For an image-only first pass, prefer:

- `draft_mode=image_only`
- `image_strategy=screenshots_only` when you only trust saved screenshots
- a source result that already contains saved local screenshots or media assets

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_draft.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>] [--draft-mode balanced|image_first|image_only]`

The request JSON should point at either a `source_result` object or a
`source_result_path`.

The draft result includes both:

- `selected_images[]`
  - direct image assets ready to embed in the article markdown
- `article_markdown`
  - a reviewable article draft with those images already inserted

Useful request flags:

- `draft_mode=image_first` when images should lead the structure
- `draft_mode=image_only` when the goal is to preserve key images with only minimal explanatory text
- `image_strategy=screenshots_only` when only screenshots should be kept
