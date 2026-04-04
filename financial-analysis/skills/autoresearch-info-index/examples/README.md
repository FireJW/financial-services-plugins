# Examples Directory

This folder contains example inputs and generated outputs for both the
recency-first `news-index` flow and the phase 1 `autoresearch-info-index`
workflow.

Use it to understand two related paths:

1. `news-index`: build a one-shot current-state result, optionally refresh it,
   and inspect the generated markdown report
2. phase 1: bridge a retrieval result into a run record, evaluate it, and
   collect evaluated outputs into one report

## Recency-First News-Index Outputs

- `news-index-crisis-request.json`
- `news-index-crisis-result.json`
- `news-index-crisis-report.md`
- `news-index-refresh-update.json`
- `news-index-crisis-refreshed.json`
- `news-index-crisis-refreshed.md`
- `news-index-crisis-run-record.json`
- `news-index-crisis-evaluated.json`
- `news-index-phase1-report.md`

These are the default generated artifacts for the single-sample recency-first
demo chain.

## Realistic Offline Fixture

- `news-index-realistic-offline-request.json`
- `news-index-realistic-offline-refresh.json`
- `fixtures/`

This fixture set is still fully deterministic and offline, but it uses more
realistic source domains, source families, conflict patterns, and local visual
artifacts than the smaller baseline demo request. Use it when you want a smoke
run that looks closer to a real geopolitical monitoring case without depending
on live web access.

Recommended smoke commands:

```text
scripts\run_news_index_realistic_demo.cmd
scripts\run_phase1_realistic_demo.cmd
scripts\run_article_workflow_realistic_demo.cmd
```

## Last30Days Bridge Fixture

- `last30days-bridge-input.json`

This request is a deterministic offline sample that treats `last30days` as a
separate upstream discovery layer and then bridges the imported findings into
`news-index`.

Recommended smoke command:

```text
scripts\run_last30days_bridge_demo.cmd
```

## Reddit Bridge Fixture

- `reddit-bridge-export-root-request.json`
- `reddit-bridge-inline-comments-request.json`
- `reddit-bridge-low-signal-request.json`
- `reddit-bridge-duplicate-comments-request.json`
- `reddit-bridge-valueinvesting-request.json`
- `fixtures/reddit-universal-scraper-sample/`

This fixture mimics the exported directory shape of
`reddit-universal-scraper`, including `data/r_*` and `data/u_*` folders with
`posts.csv`, plus optional sibling `comments.csv`.

Use it when you want to verify that `reddit-bridge` can:

- start from a higher export root instead of a single CSV path
- select a target with `subreddit`, `user`, or `export_target`
- preserve the Reddit thread permalink while keeping the outbound article URL
  in metadata
- merge `comments.csv` into post-level metadata such as `top_comment_summary`
  and `top_comment_count`
- deduplicate repeated comment snapshots conservatively so duplicate exports do
  not artificially inflate comment-sample counts
- flag suspiciously similar comments through `comment_near_duplicate_count`
  without collapsing them out of the retained sample
- preserve the caution split between same-author and cross-author near
  duplicates so operator review can tell repetition from broader meme spread
- retain a few representative `comment_near_duplicate_examples` so the warning
  can be audited without reopening the raw export immediately
- preserve partial-sample caution metadata such as
  `comment_count_mismatch` and `comment_sample_coverage_ratio`
- preserve duplicate-comment cleanup metadata such as `comment_duplicate_count`
- surface the consolidated `comment_operator_review` block that rolls sample
  coverage, duplicate cleanup, near-duplicate caution, and top-comment context
  into one bounded review object
- emit `operator_review_priority` plus a result-level `operator_review_queue`
  when you want the runtime to pre-sort which Reddit topics need manual review
  first
- preserve profile-specific metadata such as `subreddit_kind=deep_research`
  when the request targets communities like `r/ValueInvesting`
- test non-default comment ranking with `comment_sort_strategy=hybrid`

The inline-comments example is useful when the Reddit payload already nests
comment arrays under each post item and you want the bridge to preserve them
without a separate `comments.csv`.

The low-signal example is useful when you want one deterministic request that
shows `subreddit_signal:low`, partial comment-sample warnings, and top-comment
context on the same bridged observation.

The duplicate-comments example is useful when you want to verify that repeated
comment snapshots are deduplicated conservatively and still surfaced via
`comment_duplicate_count`.

The ValueInvesting example is useful when you want one deterministic request
that shows a `deep_research` subreddit profile together with near-duplicate
comment caution metadata.

Recommended smoke command:

```text
scripts\run_reddit_bridge.cmd "financial-analysis\skills\autoresearch-info-index\examples\reddit-bridge-export-root-request.json"
```

## Reddit Hot-Topic Multi-Post Fixture

- `hot-topic-reddit-multi-post-request.json`
- `tests/fixtures/reddit-hot-topic/reddit-multi-post-request.json`

This fixture is a deterministic offline sample for the `hot_topic_discovery`
surface rather than the `news-index` bridge surface.

Use it when you want to verify that Reddit topic clustering can still handle a
more realistic mixed batch with:

- same-outbound clustering
- ticker vs company-name alias clustering such as `NVDA` / `NVIDIA`
- cross-language alias clustering such as `TSMC` / `台积电`
- one unrelated standalone topic that should stay separate

Recommended smoke command:

```text
scripts\run_hot_topic_discovery.cmd "financial-analysis\skills\autoresearch-info-index\examples\hot-topic-reddit-multi-post-request.json"
```

The bounded Reddit alias layer now lives in:

- `financial-analysis/skills/autoresearch-info-index/references/reddit-cluster-aliases.json`

Use the layered keys when you need to extend it:

- `ticker_alias_groups`
- `company_alias_groups`
- `cross_language_alias_groups`

The runtime merges overlapping groups before clustering. That means entries
such as `["alphabet", "googl", "goog"]` plus `["google", "alphabet"]` still
become one bounded alias cluster instead of two competing mappings.

The subreddit community-profile layer now lives in:

- `financial-analysis/skills/autoresearch-info-index/references/reddit-community-profiles.json`

Use it when you want the bridge and `hot_topic_discovery` to classify
subreddits into bounded signal buckets such as:

- `broad_market_subreddits`
- `deep_research_subreddits`
- `speculative_flow_subreddits`
- `event_watch_subreddits`

Those profiles currently feed:

- `subreddit_kind:*` bridge tags
- `subreddit_signal:low` tags for configured low-signal communities
- bounded Reddit score multipliers and subreddit-specific overrides inside
  `hot_topic_discovery`
- normalized Reddit bridge metadata such as `subreddit_kind`,
  `reddit_listing_normalized`, `reddit_outbound_domain`,
  `top_comment_summary`, and comment-sample caution metadata
- hot-topic candidate metadata such as `reddit_subreddit_kinds`,
  `reddit_author_count`, `reddit_outbound_domains`, `top_comment_count`,
  `top_comment_author_count`, and `top_comment_max_score`

## WeChat Article Publishing

- `wechat-article-publish-demo-request.json`
- `wechat-article-push-live-request.template.json`

These fixtures cover the repo-native hot-topic-to-article publishing path.

Use the demo request when you want a deterministic export that stops before any
real WeChat API side effect:

```text
scripts\run_article_publish_demo.cmd
```

Use the live template when you want to wire a real official-account push:

1. replace the account placeholders
2. replace the cover image URL or pass `--cover-image-path`
3. confirm human review and set `human_review_approved=true`
4. set `WECHAT_APP_ID` and `WECHAT_APP_SECRET`, or pass the matching CLI flags
5. run `scripts\run_article_publish.cmd "<request.json>" --push-to-wechat`

The generated `publish-package.json` now includes:

- `draftbox_payload_template`
- `push_readiness`
- `next_push_command`
- `workflow_manual_review`
- `publication_readiness`

That means phase 1 can stop at export time without losing the exact package
shape required for the later `draft/add` step.

The generated `article-publish-result.json` and automatic acceptance artifacts
also now expose:

- `workflow_publication_gate`
- top-level `publication_readiness`
- top-level `workflow_manual_review`

So downstream reuse, regression, and operator review flows can read one
consistent gate without reconstructing it from nested package fields. Batch
queueing and auto queue now preserve that same `workflow_publication_gate`
shape as well, and the underlying workflow / macro-note outputs now expose the
same object directly.

## Article Workflow Style / Headline Tuning

- `article-workflow-style-profile-request.json`
- `fixtures/feedback-profile-english/`

Use this request when you already have a fixed indexed result and want to
exercise the writing-layer controls instead of re-running discovery:

- `source_result_path`
- `feedback_profile_dir`
- `headline_hook_mode`
- `human_signal_ratio`
- `personal_phrase_bank`

Recommended smoke command:

```text
scripts\run_article_workflow.cmd "financial-analysis\skills\autoresearch-info-index\examples\article-workflow-style-profile-request.json"
```

Canonical regression snapshots for this surface now live under:

- `tests/fixtures/article-workflow-canonical/`
- `tests/test_article_workflow_canonical_snapshots.py`

## Article Publish Acceptance Baselines

Canonical publish acceptance snapshots now live under:

- `tests/fixtures/article-publish-canonical/`
- `tests/test_article_publish_canonical_snapshots.py`

When you want the stable article workflow + publish regression pack in one shot,
run:

```text
scripts\run_article_publish_acceptance.cmd
```

## Generated Scaffold Outputs

- `batch-news-index-results/`
- `single-run-records/`
- `single-evaluated/`
- `batch-run-records/`
- `batch-evaluated/`
- `phase1-run-report.md`
- `phase1-batch-run-report.md`

These are the current scripted outputs produced by the fixed-sample phase 1
batch and single-item helper commands.

## Curated / Legacy Examples

- `trump-ceasefire-run-record.json`
- `trump-ceasefire-evaluated.json`
- `news-001-run-record.json`
- `news-001-evaluated.json`

These top-level files are standalone examples. They are useful for inspection,
but they are not the default outputs of the current single-demo script.

## Notes

- `sample-pool/` is the stable benchmark set for the evaluator path.
- `run_phase1_batch_demo.cmd` now pushes those fixed samples through the new
  recency-first retrieval front half before evaluation.
- Files ending in `-evaluated.json` are generated outputs.
- The batch directories are meant to stay small and reproducible for phase 1.
- When hard checks fail, treat evidence-confidence metrics as diagnostic context,
  not as approval to keep the candidate.
