---
name: autoresearch-info-index
description: Improve repeatable news and message indexing workflows so time-sensitive claims become easier to verify, compare, and reuse. Use when the goal is to get better at collecting fast-moving public information, separating confirmed facts from interpretation, and producing decision-useful summaries with explicit uncertainty.
---

# Autoresearch Info Index

Use this skill for repeated information-indexing workflows.

This is the task-specific layer for `autoresearch-loop` when the recurring job
is to turn fast-moving messages, headlines, or market-moving statements into a
clean, source-traceable index record.

## Use This When

- the same type of news or statement analysis happens repeatedly
- the output needs confirmed facts, explicit uncertainty, and reusable source links
- the goal is to improve the indexing process, not only to summarize one item once

Do not use this skill when:

- the task is mainly long-form company valuation
- the event cannot be tied to timestamped public sources
- there is no stable output shape to compare across runs

## Required Inputs

Before starting, collect:

- `retrieval_request`
  - `topic`
  - `analysis_time`
  - `questions[]`
  - `use_case`
  - `source_preferences[]`
  - `mode=generic|crisis`
  - `windows=[10m,1h,6h,24h]`
- source candidates with publication timestamps, source type, and claim links
- key claims that need confirmation
- current draft or baseline write-up if the run will enter phase 1 scoring
- rollback rule for unsupported or stale claims

If these are missing, the run is not ready.

## Core Rule

Never keep an indexing workflow that:

1. uses relative dates without anchoring them
2. mixes confirmed facts with interpretation
3. omits the source support behind key claims
4. hides contradictory signals from different sources

## Hard Checks

Every candidate should pass all of these:

- all time-sensitive references are anchored to absolute dates
- key claims are traceable to specific sources
- fact and inference are clearly separated
- contradictory or missing confirmations are disclosed
- source recency is checked before the conclusion is written

## Suggested Score Dimensions

- source coverage
- claim traceability
- recency discipline
- contradiction handling
- signal extraction
- retrieval efficiency

## Dual-Track Output

Every retrieval result should separate:

- `core_verdict`
- `live_tape`
- `confirmed`
- `not_confirmed`
- `inference_only`

Promotion rule:

1. one stronger-source confirmation can move a shadow signal into core evidence
2. or two independent same-tier confirmations can do the same

Demotion rule:

- evidence older than 24 hours becomes `background` unless a fresh confirming or
  contradicting signal reactivates it

Shadow signals may change monitoring priority, but they do not raise the main
confidence level by themselves.

## Structured Interfaces

Main data shapes for the recency-first front half:

- `source_observation`
  - `source_id`
  - `source_name`
  - `source_type`
  - `source_tier`
  - `channel=core|shadow|background`
  - `published_at`
  - `observed_at`
  - `url`
  - `claim_ids[]`
  - `entity_ids[]`
  - `vessel_ids[]`
  - `text_excerpt`
  - `position_hint`
  - `geo_hint`
  - `access_mode=public|browser_session|blocked`
  - `rank_score`
- `claim_ledger_entry`
  - `claim_id`
  - `claim_text`
  - `status=confirmed|denied|unclear|inferred`
  - `supporting_sources[]`
  - `contradicting_sources[]`
  - `last_updated_at`
  - `promotion_state=shadow|core|background`
- `verdict_output`
  - `core_verdict`
  - `live_tape`
  - `confidence_interval`
  - `confidence_gate`
  - `latest_signals`
  - `confirmed`
  - `not_confirmed`
  - `inference_only`
  - `conflict_matrix`
  - `missing_confirmations`
  - `market_relevance`
  - `next_watch_items`
  - `freshness_panel`
  - `source_layer_summary`
  - `background_only`
  - crisis mode also adds `negotiation_status_timeline`, `vessel_movement_table`, and `escalation_scenarios`
- `retrieval_run_report`
  - `fetch_order`
  - `sources_attempted`
  - `sources_blocked`
  - `top_recent_hits`
  - `shadow_to_core_promotions`
  - `missed_expected_source_families`

The runnable top-level result currently includes:

- `request`
- `observations`
- `claim_ledger`
- `verdict_output`
- `retrieval_run_report`
- `retrieval_quality`
- `report_markdown`

`news-index` also supports `preset=energy-war`, which forces the crisis path
and backfills an energy benchmark watchlist plus preset watch items when the
user has not supplied custom ones.

## Credibility Metrics

Every evaluated result should also expose a credibility snapshot that is easy to
aggregate later.

Prefer these metrics:

- `source_strength_score`
- `claim_confirmation_score`
- `timeliness_score`
- `agreement_score`
- `confidence_score`
- `confidence_interval`

The confidence interval is not meant to be academic precision. It is a practical
way to show when the conclusion depends on weak, sparse, or conflicting sources.

Also capture retrieval-quality metrics:

- `freshness_capture_score`
- `shadow_signal_discipline_score`
- `source_promotion_discipline_score`
- `blocked_source_handling_score`

## Recommended Workflow

1. define the topic and build a `retrieval_request`
2. discover, normalize, and rank candidate sources
3. merge duplicates and build the `claim_ledger`
4. emit the dual-track verdict
5. if this is a benchmarked loop run, bridge the result into a run record
6. evaluate the candidate against the baseline
7. keep only if hard checks pass and the score improves enough

## Crisis Mode

`mode=crisis` uses the same generic core but ships with source families and
report sections tuned for:

- negotiations and mediation claims
- public AIS or ship-tracker pages
- military movement notes using `last public indication`
- escalation scenarios with explicit triggers

Do not present exact military truth. Use wording such as `last public location`
or `last public indication`.

## Casebook References

Read the matching case file when the request clearly fits one of these repeated
patterns:

- X long post, thread, or image-first collection:
  [references/cases/x-post-first-response.md](references/cases/x-post-first-response.md)
- fast-moving negotiation, war, or military status verification:
  [references/cases/fast-moving-crisis-index.md](references/cases/fast-moving-crisis-index.md)
- turning indexed evidence into an article or publish-ready draft:
  [references/cases/index-to-article.md](references/cases/index-to-article.md)
- improving the indexing or article workflow itself with CE plus gstack:
  [references/cases/workflow-upgrade-with-ce-gstack.md](references/cases/workflow-upgrade-with-ce-gstack.md)

## Local Helper Scripts

- [scripts/python-local.cmd](scripts/python-local.cmd) runs the local D-drive Python runtime
- [scripts/news_index_runtime.py](scripts/news_index_runtime.py) contains the recency-first retrieval engine
- [scripts/news_index_core.py](scripts/news_index_core.py) is a compatibility wrapper for older imports and tests
- [scripts/news_index.py](scripts/news_index.py) builds a one-shot retrieval result
- [scripts/run_news_index.cmd](scripts/run_news_index.cmd) runs the one-shot retrieval entry
- [scripts/x_index.py](scripts/x_index.py) builds an X-post evidence pack and bridges it into the recency-first retrieval flow
- [scripts/run_x_index.cmd](scripts/run_x_index.cmd) runs the X-post evidence entry
- [scripts/macro_note_workflow.py](scripts/macro_note_workflow.py) chains `news-index/x-index -> article-brief -> macro note`
- [scripts/run_macro_note_workflow.cmd](scripts/run_macro_note_workflow.cmd) runs the macro-note workflow entry
- [scripts/last30days_bridge_runtime.py](scripts/last30days_bridge_runtime.py) imports a separate `last30days` result and bridges selected findings into `news-index` as shadow observations
- [scripts/last30days_bridge.py](scripts/last30days_bridge.py) runs the one-shot `last30days` bridge entry
- [scripts/run_last30days_bridge.cmd](scripts/run_last30days_bridge.cmd) runs the `last30days` bridge through the local Python wrapper
- [scripts/run_last30days_bridge_demo.cmd](scripts/run_last30days_bridge_demo.cmd) runs the fixed offline bridge fixture and writes result files
- [scripts/last30days_deploy_check_runtime.py](scripts/last30days_deploy_check_runtime.py) inspects whether a separate `last30days` deployment exists and which runtime/config gaps remain
- [scripts/last30days_deploy_check.py](scripts/last30days_deploy_check.py) runs the separate deployment check entry
- [scripts/run_last30days_deploy_check.cmd](scripts/run_last30days_deploy_check.cmd) runs the deployment check through the local Python wrapper
- [scripts/agent_reach_bridge_runtime.py](scripts/agent_reach_bridge_runtime.py) imports a separate Agent Reach payload or per-channel fetch result and bridges selected findings into `news-index` as shadow observations
- [scripts/agent_reach_bridge.py](scripts/agent_reach_bridge.py) runs the one-shot Agent Reach bridge entry
- [scripts/run_agent_reach_bridge.cmd](scripts/run_agent_reach_bridge.cmd) runs the Agent Reach bridge through the local Python wrapper
- [scripts/agent_reach_deploy_check_runtime.py](scripts/agent_reach_deploy_check_runtime.py) inspects whether a separate Agent Reach deployment exists, whether the core channels are actively verified, and which runtime/config gaps remain
- [scripts/agent_reach_deploy_check.py](scripts/agent_reach_deploy_check.py) runs the separate Agent Reach deployment check entry
- [scripts/run_agent_reach_deploy_check.cmd](scripts/run_agent_reach_deploy_check.cmd) runs the Agent Reach deployment check through the local Python wrapper
- [scripts/article_draft_flow_runtime.py](scripts/article_draft_flow_runtime.py) turns an x-index or news-index result into an article-ready package with citations and selected images
- [scripts/article_draft_runtime.py](scripts/article_draft_runtime.py) is a compatibility wrapper that forwards older imports to the article draft flow runtime
- [scripts/article_draft.py](scripts/article_draft.py) builds a one-shot article draft package
- [scripts/run_article_draft.cmd](scripts/run_article_draft.cmd) runs the article draft entry
- [scripts/article_workflow_runtime.py](scripts/article_workflow_runtime.py) chains indexing if needed, then builds the first draft and writes a revision template for the next review pass
- [scripts/article_workflow.py](scripts/article_workflow.py) runs the end-to-end article workflow entry
- [scripts/run_article_workflow.cmd](scripts/run_article_workflow.cmd) runs the article workflow entry through the local Python wrapper
- [scripts/macro_note_workflow_runtime.py](scripts/macro_note_workflow_runtime.py) chains indexing if needed, builds the analysis brief, and emits a macro-note result instead of a publishable article
- [scripts/macro_note_workflow.py](scripts/macro_note_workflow.py) runs the end-to-end macro note workflow entry
- [scripts/run_macro_note_workflow.cmd](scripts/run_macro_note_workflow.cmd) runs the macro note workflow entry through the local Python wrapper
- [scripts/article_batch_workflow_runtime.py](scripts/article_batch_workflow_runtime.py) runs the automatic multi-topic article queue on top of the single-article workflow
- [scripts/article_batch_workflow.py](scripts/article_batch_workflow.py) runs the batch workflow entry
- [scripts/run_article_batch_workflow.cmd](scripts/run_article_batch_workflow.cmd) runs the batch workflow through the local Python wrapper
- [scripts/article_auto_queue_runtime.py](scripts/article_auto_queue_runtime.py) ranks candidate topics by article readiness and pushes the top ones into the batch workflow
- [scripts/article_auto_queue.py](scripts/article_auto_queue.py) runs the automatic ranking entry
- [scripts/run_article_auto_queue.cmd](scripts/run_article_auto_queue.cmd) runs the automatic ranking entry through the local Python wrapper
- [scripts/hot_topic_discovery_runtime.py](scripts/hot_topic_discovery_runtime.py) fetches and ranks live hot-topic candidates before article drafting
- [scripts/hot_topic_discovery.py](scripts/hot_topic_discovery.py) runs the standalone hot-topic discovery entry
- [scripts/run_hot_topic_discovery.cmd](scripts/run_hot_topic_discovery.cmd) runs hot-topic discovery through the local Python wrapper
- [scripts/article_publish_runtime.py](scripts/article_publish_runtime.py) bridges topic discovery plus article workflow into a WeChat-ready draft package
- [scripts/article_publish.py](scripts/article_publish.py) runs the full publish entry
- [scripts/run_article_publish.cmd](scripts/run_article_publish.cmd) runs the publish flow through the local Python wrapper
- [scripts/run_article_publish_demo.cmd](scripts/run_article_publish_demo.cmd) runs the deterministic publish demo fixture end to end
- [scripts/wechat_draftbox_runtime.py](scripts/wechat_draftbox_runtime.py) uploads images and pushes a publish-package into the WeChat draft box
- [scripts/wechat_push_draft.py](scripts/wechat_push_draft.py) runs the standalone WeChat draft push entry
- [scripts/run_wechat_push_draft.cmd](scripts/run_wechat_push_draft.cmd) runs the WeChat draft push flow through the local Python wrapper
- [scripts/article_revise_flow_runtime.py](scripts/article_revise_flow_runtime.py) rebuilds a prior article draft from stored context while preserving citations and image attachments
- [scripts/article_revise_runtime.py](scripts/article_revise_runtime.py) is a compatibility wrapper that forwards older imports to the article revise flow runtime
- [scripts/article_revise.py](scripts/article_revise.py) runs one article revision pass from structured feedback
- [scripts/run_article_revise.cmd](scripts/run_article_revise.cmd) runs the article revision entry
- [scripts/run_article_workflow_tests.cmd](scripts/run_article_workflow_tests.cmd) runs the article draft/revision regression tests
- [scripts/run_news_index_demo.cmd](scripts/run_news_index_demo.cmd) runs the example one-shot request and writes result files without dumping full JSON to stdout
- [scripts/news_refresh.py](scripts/news_refresh.py) refreshes only the recent windows
- [scripts/run_news_refresh.cmd](scripts/run_news_refresh.cmd) runs the refresh entry
- [scripts/run_news_refresh_demo.cmd](scripts/run_news_refresh_demo.cmd) runs the example refresh flow and writes refreshed result files without dumping full JSON to stdout
- [scripts/news_index_to_run_record.py](scripts/news_index_to_run_record.py) bridges a retrieval result into the phase 1 run-record format
- [scripts/run_news_index_to_run_record.cmd](scripts/run_news_index_to_run_record.cmd) runs the bridge entry
- [scripts/validate_sample_pool.py](scripts/validate_sample_pool.py) validates the fixed benchmark sample set
- [scripts/run_validate_sample_pool.cmd](scripts/run_validate_sample_pool.cmd) runs the sample-pool validator
- [scripts/init_run_record.py](scripts/init_run_record.py) creates a starter run record from one benchmark item
- [scripts/run_init_run_record.cmd](scripts/run_init_run_record.cmd) runs the single-item initializer
- [scripts/init_all_run_records.py](scripts/init_all_run_records.py) creates starter run records for the full sample pool
- [scripts/run_init_all_run_records.cmd](scripts/run_init_all_run_records.cmd) runs the batch initializer
- [scripts/evaluate_info_index.py](scripts/evaluate_info_index.py) evaluates one information-index run record
- [scripts/run_evaluate_info_index.cmd](scripts/run_evaluate_info_index.cmd) runs the evaluator through the local Python wrapper
- [scripts/evaluate_all_run_records.py](scripts/evaluate_all_run_records.py) evaluates a full run-record directory
- [scripts/run_evaluate_all_run_records.cmd](scripts/run_evaluate_all_run_records.cmd) runs the batch evaluator
- [scripts/build_run_report.py](scripts/build_run_report.py) summarizes evaluated result JSON files into one Markdown report
- [scripts/run_build_run_report.cmd](scripts/run_build_run_report.cmd) runs the report builder
- [scripts/run_phase1_demo.cmd](scripts/run_phase1_demo.cmd) executes the single-sample phase 1 chain end to end and prints a compact file summary
- [scripts/run_phase1_batch_demo.cmd](scripts/run_phase1_batch_demo.cmd) upgrades the fixed sample pool through `news-index -> run-record -> evaluate` and builds the batch report
- [scripts/run_info_index_demo.cmd](scripts/run_info_index_demo.cmd) remains as a compatibility alias for the single-sample demo
- [scripts/run_news_index_tests.cmd](scripts/run_news_index_tests.cmd) runs the recency-first retrieval regression tests

Keep the local batch evaluator flow parallel to `autoresearch-code-fix`:
validated sample pool, batch run-record generation, batch evaluation, then one
markdown report.

## References

- [references/scoring.md](references/scoring.md)
- [references/verification-checklist.md](references/verification-checklist.md)
