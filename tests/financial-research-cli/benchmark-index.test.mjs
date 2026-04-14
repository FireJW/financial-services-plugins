import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("benchmark-index emits stable contract envelope", () => {
  const result = runCli(
    [
      "benchmark-index",
      "--input",
      "apps/financial-research-cli/examples/benchmark-index-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "benchmark-index": {
          status: "ok",
          workflow_kind: "benchmark_index",
          summary: {
            loaded_cases: 6,
            considered_cases: 6,
            threshold_qualified_cases: 5,
            exception_qualified_cases: 1,
            candidate_queue_excluded: 0,
          },
          cases: [
            {
              case_id: "jinrongbaguanv-toutiao",
              classification: "acquisition",
            },
          ],
          report_path: "out/benchmark-index-report.md",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "benchmark-index");
  assert.equal(payload.workflow_kind, "benchmark_index");
  assert.equal(payload.summary.considered_cases, 6);
  assert.equal(payload.summary.threshold_qualified_cases, 5);
  assert.equal(payload.summary.top_case_id, "jinrongbaguanv-toutiao");
  assert.equal(payload.plugin_surface.skill_id, "decision-journal-publishing");
  assert.match(payload.execution_target.wrapper, /decision-journal-publishing[\\/]scripts[\\/]run_benchmark_index\.cmd$/);
});

test("benchmark-index dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "benchmark-index",
    "--input",
    "request.json",
    "--output",
    "out/benchmark-index.json",
    "--markdown-output",
    "out/benchmark-index.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/benchmark-index.json",
    "--markdown-output",
    "out/benchmark-index.md",
  ]);
  assert.match(payload.execution_plan.wrapper, /decision-journal-publishing[\\/]scripts[\\/]run_benchmark_index\.cmd$/);
});

test("benchmark-index requires an input path", () => {
  const result = runCli(["benchmark-index"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for benchmark-index/);
});
