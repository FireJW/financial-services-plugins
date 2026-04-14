import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("all commands share the same contract envelope keys", () => {
  const scenarios = [
    {
      command: "agent-reach-deploy-check",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ready",
        workflow_kind: "agent_reach_deploy_check",
        install_root: "fixtures/agent-reach/install",
        pseudo_home: "fixtures/agent-reach/pseudo-home",
        python_status: { status: "ok" },
        binaries: {
          "agent-reach": "ok",
          gh: "ok",
          "yt-dlp": "ok",
          node: "ok",
          npm: "ok",
        },
        channels: {
          web_jina: "ok",
          github: "ok",
          rss: "ok",
        },
        channels_failed: [],
        credential_gaps: [],
        core_channels_ready: true,
      },
    },
    {
      command: "agent-reach-bridge",
      args: ["--input", "agent-reach.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "agent_reach_bridge",
        topic: "Huawei AI chip orders",
        channels_attempted: ["github", "youtube"],
        channels_succeeded: ["github", "youtube"],
        channels_failed: [],
        observations_imported: 2,
        observations_skipped_duplicate: 0,
        retrieval_result: {
          observations: [{ url: "https://github.com/example/huawei-chip-watch" }],
        },
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
      },
    },
    {
      command: "article-publish",
      args: ["--input", "publish-request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_publish",
        publication_readiness: "ready",
        workflow_manual_review: { status: "not_required" },
        push_stage: { status: "not_requested" },
        publish_package: {
          title: "AI Agent hiring rebound becomes a business story",
          push_readiness: { status: "missing_cover_image" },
        },
        publish_package_path: "out/publish-package.json",
      },
    },
    {
      command: "article-publish-reuse",
      args: ["--base-publish-result", "base.json", "--revised-article-result", "revised.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_publish_reuse",
        publication_readiness: "ready",
        workflow_manual_review: { status: "not_required" },
        automatic_acceptance: { status: "accepted" },
        publish_package_path: "out/reuse-package.json",
      },
    },
    {
      command: "article-batch",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_batch_workflow",
        total_items: 2,
        succeeded_items: 2,
        failed_items: 0,
        publication_readiness: "ready",
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
        items: [{ label: "news-request", quality_gate: "pass" }],
      },
    },
    {
      command: "article-auto-queue",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_auto_queue",
        candidate_count: 2,
        selected_count: 1,
        publication_readiness: "ready",
        batch_result: { status: "ok" },
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
        ranked_candidates: [{ label: "news-request-candidate", selection_status: "selected" }],
      },
    },
    {
      command: "article-brief",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_brief",
        request: { topic: "Hormuz negotiation realistic offline fixture" },
        source_summary: { topic: "Hormuz negotiation realistic offline fixture", source_kind: "news_index" },
        supporting_citations: [{ citation_id: "S1" }, { citation_id: "S2" }],
        analysis_brief: {
          canonical_facts: [{ claim_text: "Indirect contacts continue." }],
          not_proven: [{ claim_text: "A finalized settlement exists." }],
          story_angles: [{ angle: "Negotiation vs settlement boundary" }],
          recommended_thesis: "Indirect contacts continue, but a finalized settlement is still not confirmed.",
        },
      },
    },
    {
      command: "article-draft",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_draft",
        request: { topic: "Hormuz negotiation realistic offline fixture" },
        source_summary: { topic: "Hormuz negotiation realistic offline fixture", source_kind: "news_index" },
        article_package: {
          title: "Hormuz negotiation realistic offline fixture",
          draft_mode: "balanced",
          draft_thesis: "Indirect contacts continue, but a finalized settlement is still not confirmed.",
          selected_images: [],
          citations: [{ citation_id: "S1" }, { citation_id: "S2" }],
        },
      },
    },
    {
      command: "article-workflow",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_workflow",
        topic: "Hormuz negotiation realistic offline fixture",
        publication_readiness: "ready",
        source_stage: { source_kind: "news_index" },
        final_stage: { quality_gate: "pass" },
        final_article_result_path: "out/final-article-result.json",
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
      },
    },
    {
      command: "benchmark-index",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "benchmark_index",
        summary: {
          loaded_cases: 6,
          considered_cases: 6,
          threshold_qualified_cases: 5,
          exception_qualified_cases: 1,
          candidate_queue_excluded: 0,
        },
        cases: [{ case_id: "jinrongbaguanv-toutiao", classification: "acquisition" }],
        report_path: "out/benchmark-index-report.md",
      },
    },
    {
      command: "benchmark-readiness",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "benchmark_readiness_audit",
        readiness_level: "warning",
        ready_for_daily_refresh: true,
        summary: {
          reviewed_cases: 1,
          candidate_cases: 1,
          enabled_seed_sources: 1,
        },
        blockers: [],
        warnings: ["Candidate inbox is currently empty."],
      },
    },
    {
      command: "benchmark-refresh",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "benchmark_library_refresh",
        summary: {
          reviewed_cases_refreshed: 1,
          candidate_cases_refreshed: 0,
          candidates_discovered: 1,
          matched_existing_cases: 0,
          source_failures: 0,
        },
        benchmark_index_result: {
          summary: {
            considered_cases: 1,
          },
        },
        report_path: "out/benchmark-refresh-report.md",
      },
    },
    {
      command: "morning-note",
      args: ["--input", "input.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "macro_note_workflow",
        topic: "Topic",
        publication_readiness: "ready",
        workflow_publication_gate: { manual_review: { status: "not_required" } },
        macro_note_stage: { result_path: "out/macro.json" },
        operator_summary_path: "out/operator-summary.json",
      },
    },
    {
      command: "completion-check",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ready",
        workflow_kind: "x_index",
        recommendation: "proceed",
        blockers: [],
        warnings: ["session fallback used"],
        target: "out/x-index-result.json",
      },
    },
    {
      command: "earnings-update",
      args: ["--input", "input.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "article_workflow",
        publication_readiness: "ready",
        source_stage: { source_kind: "news_index" },
        final_stage: { quality_gate: "pass" },
        final_article_result_path: "out/article.json",
        operator_summary_path: "out/operator-summary.json",
      },
    },
    {
      command: "eval-harness",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "x_index",
        target: "out/x-index-result.json",
        findings: [{ severity: "medium", message: "session visible" }],
        summary: {
          recommendation: "accept_with_notes",
          average_score: 84,
        },
      },
    },
    {
      command: "fieldtheory-index",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "fieldtheory_bookmark_index",
        topic: "Karpathy systems bottleneck",
        fieldtheory_summary: {
          status: "ok",
          bookmarks_path: "out/bookmarks.jsonl",
          matched_count: 1,
          selected_count: 1,
        },
        matches: [{ post_url: "https://x.com/karpathy/status/111" }],
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
      },
    },
    {
      command: "last30days-deploy-check",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ready",
        workflow_kind: "last30days_deploy_check",
        skill_root: "fixtures/last30days/install",
        required_files: [
          { relative_path: "SKILL.md", exists: true },
          { relative_path: "README.md", exists: true },
          { relative_path: "scripts/last30days.py", exists: true },
        ],
        binary_status: {
          required_groups: [],
          optional: [{ command: "node", available: true }],
        },
        env_status: { env_file: { exists: true } },
        sqlite_candidates: ["fixtures/last30days/data/history.sqlite"],
      },
    },
    {
      command: "last30days-bridge",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "last30days_bridge",
        request: {
          topic: "Hormuz escalation and regional mediation watch",
          result_path: "fixtures/last30days-bridge-input.json",
        },
        import_summary: {
          raw_item_count: 4,
          imported_candidate_count: 4,
          batch_labels: ["findings", "web", "polymarket"],
          blocked_count: 1,
          with_artifacts: 1,
        },
        retrieval_result: {
          observations: [{ url: "https://x.com/sentdefender/status/2036153038906196133" }],
        },
      },
    },
    {
      command: "opencli-index",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "opencli_bridge",
        request: {
          topic: "China aluminum broker note check",
          site_profile: "broker-research-portal",
          payload_source: "result_path",
        },
        import_summary: {
          payload_source: "result_path",
          imported_candidate_count: 2,
          skipped_duplicate_count: 0,
          artifact_count: 0,
        },
        runner_summary: { status: "not_run" },
        retrieval_result: {
          observations: [{ url: "https://research.example.com/china-aluminum-note" }],
        },
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
      },
    },
    {
      command: "reddit-bridge",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "reddit_bridge",
        topic: "NVIDIA Blackwell retail read-through",
        import_summary: {
          payload_source: "csv_export_root",
          source_path: "out/r_stocks/posts.csv",
          imported_candidate_count: 1,
          comment_sample_count: 2,
          operator_review_required_count: 0,
        },
        retrieval_result: {
          observations: [{ url: "https://www.reddit.com/r/stocks/comments/nvda123/thread/" }],
        },
        operator_review_queue: [],
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "warning" },
      },
    },
    {
      command: "theme-screen",
      args: ["--topic", "agents", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "hot_topic_discovery",
        ranked_topics: [],
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
      },
    },
    {
      command: "wechat-draft-push",
      args: ["--input", "publish-package.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "wechat_draft_push",
        push_backend: "api",
        review_gate: { status: "approved" },
        workflow_publication_gate: { publication_readiness: "ready" },
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
        draft_result: { media_id: "draft-123" },
      },
    },
    {
      command: "wechat-push-readiness",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "wechat_push_readiness_audit",
        readiness_level: "ready",
        ready_for_real_push: true,
        push_readiness: { status: "ready_for_api_push" },
        credential_check: { status: "ready" },
        live_auth_check: { status: "not_run" },
        workflow_publication_gate: { publication_readiness: "ready" },
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "ready" },
      },
    },
    {
      command: "x-index",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "x_index",
        request: { topic: "X macro watchlist snapshot" },
        session_bootstrap: { source: "cookie_file", status: "ready" },
        fieldtheory_summary: { status: "ok", matched_count: 1, selected_count: 1 },
        x_posts: [{ post_url: "https://x.com/example/status/4200000000000000000" }],
        completion_check: { status: "ready" },
        operator_summary: { operator_status: "warning" },
      },
    },
    {
      command: "operator-summary",
      args: ["--input", "request.json", "--json"],
      payload: {
        status: "ok",
        workflow_kind: "x_index",
        operator_status: "warning",
        operator_recommendation: "review_before_proceed",
        target: "x-index-result.json",
        completion_check: { status: "ready" },
        eval_harness: { recommendation: "review_before_reuse" },
      },
    },
  ];

  for (const scenario of scenarios) {
    const result = runCli([scenario.command, ...scenario.args], {
      runner: makeRunner({ [scenario.command]: scenario.payload }),
    });

    assert.equal(result.exitCode, 0, result.stderr);
    const payload = parseStdoutJson(result);
    assert.equal(typeof payload.cli_command, "string");
    assert.equal(typeof payload.status, "string");
    assert.equal(typeof payload.workflow_kind, "string");
    assert.equal(typeof payload.input_path, "string");
    assert.equal(typeof payload.plugin_surface, "object");
    assert.equal(typeof payload.execution_target, "object");
    assert.equal(typeof payload.summary, "object");
    assert.equal(typeof payload.result, "object");
  }
});

test("help text lists the current phase-c commands", () => {
  const result = runCli(["--help"]);
  assert.equal(result.exitCode, 0, result.stderr);
  assert.match(result.stdout, /morning-note/);
  assert.match(result.stdout, /agent-reach-deploy-check/);
  assert.match(result.stdout, /agent-reach-bridge/);
  assert.match(result.stdout, /article-auto-queue/);
  assert.match(result.stdout, /article-batch/);
  assert.match(result.stdout, /article-brief/);
  assert.match(result.stdout, /article-draft/);
  assert.match(result.stdout, /article-workflow/);
  assert.match(result.stdout, /completion-check/);
  assert.match(result.stdout, /benchmark-index/);
  assert.match(result.stdout, /benchmark-readiness/);
  assert.match(result.stdout, /benchmark-refresh/);
  assert.match(result.stdout, /catalog/);
  assert.match(result.stdout, /plugin-catalog/);
  assert.match(result.stdout, /earnings-update/);
  assert.match(result.stdout, /eval-harness/);
  assert.match(result.stdout, /fieldtheory-index/);
  assert.match(result.stdout, /last30days-deploy-check/);
  assert.match(result.stdout, /last30days-bridge/);
  assert.match(result.stdout, /opencli-index/);
  assert.match(result.stdout, /reddit-bridge/);
  assert.match(result.stdout, /source-intake/);
  assert.match(result.stdout, /theme-screen/);
  assert.match(result.stdout, /wechat-draft-push/);
  assert.match(result.stdout, /wechat-push-readiness/);
  assert.match(result.stdout, /x-index/);
  assert.match(result.stdout, /article-publish/);
  assert.match(result.stdout, /article-publish-reuse/);
  assert.match(result.stdout, /operator-summary/);
  assert.match(result.stdout, /fieldtheory/);
});
