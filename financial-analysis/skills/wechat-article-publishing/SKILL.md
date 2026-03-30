---
name: wechat-article-publishing
description: Turn a hot topic or a user-specified topic into a WeChat Official Account article draft package. Use when the user asks to write a public-account article, discover what is worth writing today, export WeChat-compatible HTML, or prepare content that will later be pushed to the WeChat draft box API.
---

# WeChat Article Publishing

Use this skill when the user says things like:

- 写一篇公众号文章
- 自动抓热点然后写成公众号草稿
- 帮我做一个微信公众平台可发布的版本
- 先找今天值得写的题，再写成文章

## Core Rule

Do not bypass the repository's evidence workflow.

Preferred path:

1. discover or choose a topic
2. turn it into a `news-index` request
3. run `article-workflow`
4. export a stable WeChat draft package
5. keep future API upload steps explicit instead of pretending the draft is
   already fully push-ready

## Default Behavior

If the user gives no topic:

1. run hot-topic discovery
2. rank the candidates
3. pick the strongest one unless the user wants to choose manually

If the user gives a topic:

1. use that topic as the query seed
2. collect enough public sources to build the evidence package
3. continue into the same article workflow

## Output Requirements

The output should include:

1. the selected topic and why it won
2. the evidence-backed article workflow result
3. a WeChat-compatible HTML draft
4. digest and keyword metadata
5. image-upload placeholders that are stable enough for a future WeChat Draft
   API bridge

## Local Helpers

- [scripts/run_hot_topic_discovery.cmd](../autoresearch-info-index/scripts/run_hot_topic_discovery.cmd)
- [scripts/run_article_publish.cmd](../autoresearch-info-index/scripts/run_article_publish.cmd)
- [scripts/run_wechat_push_draft.cmd](../autoresearch-info-index/scripts/run_wechat_push_draft.cmd)

## Operator Notes

- [references/founder-ceo-review.md](references/founder-ceo-review.md) explains why
  the last mile should stay human-controlled even when the push tooling is real

Phase 1 is allowed to stop at:

1. reviewable content HTML
2. draft payload template
3. explicit unresolved upload placeholders such as `thumb_media_id`

Phase 1 should not fake:

1. uploaded WeChat media IDs
2. API success
3. inline image URLs that do not really exist

Phase 2 can continue into a real WeChat draft push when:

1. `push_to_wechat=true`
2. `human_review_approved=true`
3. `wechat_app_id` and `wechat_app_secret` are available, or the matching env
   vars are set
4. the package has a usable cover image or an explicit cover override
