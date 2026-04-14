import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("completion-check emits stable contract envelope", () => {
  const result = runCli(
    [
      "completion-check",
      "--input",
      "apps/financial-research-cli/examples/completion-check-x-index-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "completion-check": {
          status: "ready",
          workflow_kind: "x_index",
          recommendation: "proceed",
          blockers: [],
          warnings: ["browser session fell back to cookie_file"],
          target: "apps/financial-research-cli/.smoke/x-index/x-index-result.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "completion-check");
  assert.equal(payload.summary.completion_status, "ready");
  assert.equal(payload.summary.recommendation, "proceed");
  assert.equal(payload.summary.warning_count, 1);
  assert.match(payload.execution_target.wrapper, /run_completion_check\.cmd$/);
});

test("completion-check dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "completion-check",
    "--input",
    "request.json",
    "--markdown-output",
    "out/completion-check.md",
    "--output",
    "out/completion-check.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/completion-check.json",
    "--markdown-output",
    "out/completion-check.md",
  ]);
});

test("completion-check requires an input path", () => {
  const result = runCli(["completion-check"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for completion-check/);
});
