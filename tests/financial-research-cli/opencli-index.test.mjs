import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("opencli-index emits stable contract envelope", () => {
  const result = runCli(
    [
      "opencli-index",
      "--input",
      "apps/financial-research-cli/examples/opencli-index-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "opencli-index": {
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
          runner_summary: {
            status: "not_run",
          },
          retrieval_result: {
            observations: [
              {
                url: "https://research.example.com/china-aluminum-note",
              },
            ],
          },
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "warning" },
          completion_check_path: "out/opencli-index-completion-check.json",
          operator_summary_path: "out/opencli-index-operator-summary.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "opencli-index");
  assert.equal(payload.workflow_kind, "opencli_bridge");
  assert.equal(payload.summary.site_profile, "broker-research-portal");
  assert.equal(payload.summary.imported_count, 2);
  assert.equal(payload.summary.runner_status, "not_run");
  assert.match(payload.execution_target.wrapper, /run_opencli_bridge\.cmd$/);
});

test("opencli-index dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "opencli-index",
    "--input",
    "request.json",
    "--output",
    "out/opencli-index.json",
    "--markdown-output",
    "out/opencli-index.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/opencli-index.json",
    "--markdown-output",
    "out/opencli-index.md",
  ]);
});

test("opencli-index requires an input path", () => {
  const result = runCli(["opencli-index"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for opencli-index/);
});
