import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("eval-harness emits stable contract envelope", () => {
  const result = runCli(
    [
      "eval-harness",
      "--input",
      "apps/financial-research-cli/examples/eval-harness-x-index-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "eval-harness": {
          status: "ok",
          workflow_kind: "x_index",
          findings: [{ severity: "medium", message: "browser session status is ready" }],
          summary: {
            recommendation: "accept_with_notes",
            average_score: 84,
          },
          target: "apps/financial-research-cli/.smoke/x-index/x-index-result.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "eval-harness");
  assert.equal(payload.summary.recommendation, "accept_with_notes");
  assert.equal(payload.summary.average_score, 84);
  assert.equal(payload.summary.finding_count, 1);
  assert.match(payload.execution_target.wrapper, /run_eval_harness\.cmd$/);
});

test("eval-harness dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "eval-harness",
    "--input",
    "request.json",
    "--markdown-output",
    "out/eval-harness.md",
    "--output",
    "out/eval-harness.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/eval-harness.json",
    "--markdown-output",
    "out/eval-harness.md",
  ]);
});

test("eval-harness requires an input path", () => {
  const result = runCli(["eval-harness"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for eval-harness/);
});
