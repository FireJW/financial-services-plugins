---
description: Import exported Reddit results as shadow observations and bridge them into news-index
argument-hint: "[request-json]"
---

# Reddit Bridge Command

Use this command when you already have Reddit post exports or a Reddit result
payload and want to feed that community signal into the current recency-first
workflow without replacing the repo's evidence firewall.

This command should:

1. read a saved Reddit export, exported directory, or bridge request
2. normalize supported Reddit posts into `news-index` candidates
3. import them as `shadow` by default with `origin=reddit_bridge`
4. run `news-index` on top of that imported candidate set
5. return both the import summary and the bridged `retrieval_result`

Default expectations:

- imported Reddit findings stay `shadow` by default
- imported Reddit findings keep `origin=reddit_bridge`
- subreddit, permalink, title, and body-text context are preserved when present
- when a Reddit export also contains an outbound article URL, the bridge keeps
  the Reddit thread permalink as the source URL and preserves the outbound URL
  in metadata
- normalized bridge metadata should preserve bounded community-signal fields
  such as subreddit kind, listing window, author, and outbound domain when
  available
- when a sibling `comments.csv` exists, the bridge should fold top-comment
  context into metadata such as `top_comment_summary`, `top_comment_excerpt`,
  and `top_comment_count`
- repeated comment snapshots should be deduplicated conservatively before the
  bridge turns them into top-comment metadata, and any collapsed duplicates
  should remain visible through `comment_duplicate_count`
- suspiciously similar comments should stay in the sample but surface
  `comment_near_duplicate_count` as a caution signal instead of silently
  collapsing into the exact-dedup path
- near-duplicate cautions should preserve
  `comment_near_duplicate_same_author_count`,
  `comment_near_duplicate_cross_author_count`, and
  `comment_near_duplicate_level` so operator review can distinguish author
  self-rephrasing from cross-author repetition
- when near-duplicate cautions exist, the bridge may also retain a few bounded
  `comment_near_duplicate_examples` for manual review
- comment imports may use bounded sorting via `comment_sort_strategy`
  (`score_then_recency`, `recency_then_score`, `hybrid`) when the operator
  wants fresher replies to compete with high-score older replies
- when the declared post comment count is much larger than the imported sample,
  the bridge should preserve `comment_count_mismatch`,
  `comment_sample_coverage_ratio`, and `comment_sample_status=partial`
- when comment-layer caution metadata exists, the bridge should also emit a
  bounded `comment_operator_review` block so downstream consumers can read one
  structured review object instead of reconstructing caution state field by
  field
- when the bridge sees enough caution to warrant follow-up, it should also emit
  `operator_review_priority` and a top-level `operator_review_queue` so
  operators can pull the highest-risk Reddit imports first
- Reddit engagement can help downstream topic discovery, but does not count as
  claim confirmation by itself
- this route is for result ingestion, not for replacing the native `x-index`
  or other signed-session workflows

Local helpers:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_reddit_bridge.cmd [request.json] [--file <result-path-or-directory>] [--topic <query>] [--output <result.json>] [--markdown-output <report.md>]`

Suggested use cases:

- import a `posts.csv` export from a separate Reddit scraper
- import a `posts.csv` plus sibling `comments.csv` export when you want the
  bridge to preserve the post's top-comment read-through
- import a Reddit scraper export root such as `.../data/r_<subreddit>/posts.csv`
  or `.../data/u_<user>/posts.csv`
- import a saved Reddit JSON payload with `posts` or `items`
- import a JSON payload where each post already carries nested `comments`
- bridge Reddit community discussion into `news-index`, article prep, or topic
  triage without adding a new scoring core
- preserve enough metadata for later operator review, including
  `subreddit_kind:*`, `listing:*`, `listing_window:*`, and outbound domain tags
- preserve bounded community-risk signals such as `subreddit_signal:low` and
  any configured subreddit score overrides without upgrading Reddit into a
  verdict-bearing source
- preserve comment-layer caution tags such as `comment_sample:partial`,
  `comment_near_duplicate`, and non-default comment sort tags such as
  `comment_sort:hybrid`

Directory-selection notes:

- if `--file` points directly at a target directory that already contains
  `posts.csv`, the bridge imports it directly
- if `--file` points at a higher export root, the bridge will auto-discover
  `data/r_*` and `data/u_*` targets
- if that export root contains multiple targets, pass `subreddit`, `user`, or
  `export_target` in the request JSON so the bridge picks the intended folder

Useful request knobs:

- `comment_sort_strategy`
  - default: `score_then_recency`
  - `recency_then_score` when you care more about the freshest reaction
  - `hybrid` when you want fresher high-quality replies to outrank slightly
    older comments with only a small score edge
