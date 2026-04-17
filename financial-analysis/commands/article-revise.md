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

Manual edit behavior:

- `edited_body_markdown` and `edited_article_markdown` are preserved by default
- set `allow_auto_rewrite_after_manual=true` only when you want the system to red-team your manual draft and then generate a safer rewritten version
- `human_feedback_form` is now the preferred review path because it is simpler than the lower-level structured fields
- `edit_reason_feedback` lets you explain what you changed and why, so later workflow learning can rely on your explicit reasons instead of only guessing from the diff

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
- `edited_article_markdown`
  - replace the full article markdown while keeping the evidence package attached
- `human_feedback_form.overall_goal_in_plain_english`
  - one sentence saying what you were trying to improve
- `human_feedback_form.what_to_keep[]`
  - optional soft keep-notes for context you want preserved; this is guidance, not a hard lock
- `human_feedback_form.what_to_change[]`
  - plain-language change requests like `change="Lead with confirmed facts first"`, `why="Readers should see what is known before scenarios"`; `area`, `reason_tag`, and `remember_for` are optional
- `human_feedback_form.what_to_remember_next_time[]`
  - only stable preferences you want remembered later, like `key=must_include`, `value="Lead with the strongest confirmed fact before any scenario."`; if you omit `scope`, topic-level memory is assumed
- `human_feedback_form.one_off_fixes_not_style[]`
  - fact or evidence corrections that should stay one-off and not become house style
- `edit_reason_feedback.summary`
  - one plain-language sentence about the overall reason for the revision
- `edit_reason_feedback.changes[]`
  - structured human change reasons, for example `area=body`, `reason_tag=clarity`, `why="Lead with confirmed facts first"`, `reuse_scope=topic`
- `edit_reason_feedback.reusable_preferences[]`
  - optional reusable preferences, for example `key=must_include`, `value="Lead with the strongest confirmed fact before any scenario."`, `scope=topic`
- `allow_auto_rewrite_after_manual`
  - default `false`; opt in only if you want automatic rewrite after the manual draft is reviewed

This command is designed for the review loop:

- first generate an image-aware article package
- then revise it without losing the saved screenshots, media, or source links
- keep stacking revision history so later workflow tuning has concrete feedback to learn from
- when the full article workflow runs, it also writes `article-revise-form.md` as a human-readable companion to the JSON template
- the full workflow now also writes `ARTICLE-FEEDBACK.md`, which is the preferred editable markdown review file

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_revise.cmd "<article-draft-result.json>" "<ARTICLE-FEEDBACK.md or request.json>" [--output <result.json>] [--markdown-output <report.md>] [--draft-mode balanced|image_first|image_only]`

The request JSON should point at either an `article_result` object or an
`article_result_path`.

Useful request fields:

- `pinned_image_ids[]` or `feedback.keep_image_asset_ids[]` to keep specific images at the front
- `drop_image_ids[]` or `feedback.drop_image_asset_ids[]` to remove specific images
- `draft_mode=image_only` to keep the article minimal and image-led
- `human_feedback_form`
  - preferred top-level review form; easiest path for human editing feedback
- `edit_reason_feedback`
  - advanced lower-level version of the same idea; use this only if you want the machine-structured fields directly
