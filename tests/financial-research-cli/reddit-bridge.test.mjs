import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("reddit-bridge emits stable contract envelope", () => {
  const result = runCli(
    [
      "reddit-bridge",
      "--input",
      "apps/financial-research-cli/examples/reddit-bridge-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "reddit-bridge": {
          status: "ok",
          workflow_kind: "reddit_bridge",
          topic: "NVIDIA Blackwell retail read-through",
          import_summary: {
            payload_source: "csv_export_root",
            source_path:
              "financial-analysis/skills/autoresearch-info-index/examples/fixtures/reddit-universal-scraper-sample/data/r_stocks/posts.csv",
            imported_candidate_count: 1,
            comment_sample_count: 2,
            operator_review_required_count: 0,
          },
          retrieval_result: {
            observations: [
              {
                url: "https://www.reddit.com/r/stocks/comments/nvda123/nvidia_blackwell_demand_thread/",
              },
            ],
          },
          operator_review_queue: [],
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "warning" },
          completion_check_path: "out/reddit-bridge-completion-check.json",
          operator_summary_path: "out/reddit-bridge-operator-summary.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "reddit-bridge");
  assert.equal(payload.workflow_kind, "reddit_bridge");
  assert.equal(payload.summary.payload_source, "csv_export_root");
  assert.equal(payload.summary.imported_count, 1);
  assert.equal(payload.summary.comment_sample_count, 2);
  assert.match(payload.execution_target.wrapper, /run_reddit_bridge\.cmd$/);
});

test("reddit-bridge dry-run supports input or direct file routing", () => {
  const result = runCli([
    "reddit-bridge",
    "--file",
    "reddit-export-root",
    "--topic",
    "Retail AI infra read-through",
    "--output",
    "out/reddit-bridge.json",
    "--markdown-output",
    "out/reddit-bridge.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "--file",
    "reddit-export-root",
    "--topic",
    "Retail AI infra read-through",
    "--output",
    "out/reddit-bridge.json",
    "--markdown-output",
    "out/reddit-bridge.md",
  ]);
});

test("reddit-bridge requires input or file", () => {
  const result = runCli(["reddit-bridge"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /reddit-bridge requires --input <path> or --file <path>/);
});
