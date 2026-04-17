import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("fieldtheory-index emits stable contract envelope", () => {
  const result = runCli(
    [
      "fieldtheory-index",
      "--input",
      "apps/financial-research-cli/examples/fieldtheory-index-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "fieldtheory-index": {
          status: "ok",
          workflow_kind: "fieldtheory_bookmark_index",
          topic: "Karpathy systems bottleneck",
          fieldtheory_summary: {
            status: "ok",
            bookmarks_path: "apps/financial-research-cli/examples/fixtures/fieldtheory-bookmarks.jsonl",
            matched_count: 1,
            selected_count: 1,
          },
          matches: [
            {
              post_url: "https://x.com/karpathy/status/111",
            },
          ],
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "ready" },
          completion_check_path: "out/fieldtheory-index-completion-check.json",
          operator_summary_path: "out/fieldtheory-index-operator-summary.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "fieldtheory-index");
  assert.equal(payload.workflow_kind, "fieldtheory_bookmark_index");
  assert.equal(payload.summary.lookup_status, "ok");
  assert.equal(payload.summary.matched_count, 1);
  assert.equal(payload.summary.selected_count, 1);
  assert.match(payload.execution_target.wrapper, /run_fieldtheory_bookmark_index\.cmd$/);
});

test("fieldtheory-index dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "fieldtheory-index",
    "--input",
    "request.json",
    "--output",
    "out/fieldtheory-index.json",
    "--markdown-output",
    "out/fieldtheory-index.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/fieldtheory-index.json",
    "--markdown-output",
    "out/fieldtheory-index.md",
  ]);
});

test("fieldtheory-index requires an input path", () => {
  const result = runCli(["fieldtheory-index"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for fieldtheory-index/);
});
