---
description: Discover a hot topic or use a provided topic, run the article workflow, and export a WeChat-ready draft package
argument-hint: "[publish-request-json]"
---

# Article Publish Command

Use this command when the goal is not just to draft an article, but to move all
the way into a WeChat-publication-ready package:

1. discover hot topics from live feeds, or use a user-provided topic
2. rank and pick the strongest topic
3. build the evidence-backed article workflow package
4. export WeChat-compatible HTML plus a draftbox payload template
5. if requested, upload assets and create a real WeChat draft

This command is the repo-native bridge between:

- hot topic discovery
- `news-index`
- `article-workflow`
- future WeChat draftbox API publishing

Typical uses:

- `写一篇公众号文章`
- `写一篇关于 AI Agent 开发趋势的公众号文章`
- `给我自动抓热点，写成公众号草稿`

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_publish.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`
- `financial-analysis\skills\autoresearch-info-index\scripts\run_article_publish_demo.cmd`

Useful request fields:

- `topic`
  - optional explicit topic override
- `manual_topic_candidates[]`
  - optional offline or deterministic topic fixtures
- `sources[]`
  - optional discovery source override such as `weibo`, `zhihu`, `36kr`, `google-news-world`, or `google-news-search`
- `draft_mode`
  - `balanced`, `image_first`, or `image_only`
- `image_strategy`
  - `mixed`, `prefer_images`, or `screenshots_only`
- `account_name`
  - optional public-account name for the export package
- `author`
  - optional author field for the future WeChat payload
- `push_to_wechat`
  - when `true`, the workflow will attempt a real WeChat Draft API push
- `human_review_approved`
  - required for a real WeChat push; keeps export and real side effects separate
- `human_review_approved_by` / `human_review_note`
  - optional reviewer name and review note recorded with the push gate
- `wechat_app_id` / `wechat_app_secret`
  - explicit credentials, or use `WECHAT_APP_ID` / `WECHAT_APP_SECRET`
- `cover_image_path` / `cover_image_url`
  - optional explicit cover override if the article package has no usable hero image

The output package includes:

- ranked topic selection
- the generated `news-index` request
- the full article workflow result
- a `publish-package.json` with `workflow_manual_review` plus
  `publication_readiness`
- an `article-publish-result.json` / markdown report with a top-level
  `workflow_publication_gate`
- a `wechat-draft.html`
- a `draftbox_payload_template`
- automatic acceptance JSON / markdown artifacts that preserve the same
  workflow publication gate
- a `push_readiness` block that tells you whether the later WeChat push step is blocked by content, cover image, or credentials
- when push is requested and succeeds, a `wechat-push-result.json`

Useful direct CLI flags:

- `--sources weibo zhihu 36kr google-news-search`
- `--selected-topic-index 2`
- `--author "<name>"`
- `--account-name "<account>"`
- `--show-cover-pic 1`
- `--cover-image-path "<local-file>"`
- `--human-review-approved --human-review-approved-by "<reviewer>"`

Phase-1 expectation:

- content HTML should be reviewable and reusable immediately
- WeChat upload placeholders should remain stable
- `thumb_media_id` and any local-only inline images are still left as explicit
  future API steps instead of being faked

Phase-2 expectation:

- `push_to_wechat=true` uploads article images through WeChat first
- real push is blocked until `human_review_approved=true`
- the final HTML sent to `draft/add` should already contain WeChat-hosted image URLs
- cover upload and `thumb_media_id` resolution happen inside the same push step
