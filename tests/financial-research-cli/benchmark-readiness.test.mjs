import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("benchmark-readiness emits stable contract envelope", () => {
  const result = runCli(
    [
      "benchmark-readiness",
      "--input",
      "apps/financial-research-cli/examples/benchmark-readiness-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "benchmark-readiness": {
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
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "benchmark-readiness");
  assert.equal(payload.workflow_kind, "benchmark_readiness_audit");
  assert.equal(payload.summary.readiness_level, "warning");
  assert.equal(payload.summary.warning_count, 1);
  assert.equal(payload.summary.enabled_seed_sources, 1);
  assert.equal(payload.plugin_surface.skill_id, "decision-journal-publishing");
  assert.match(payload.execution_target.wrapper, /decision-journal-publishing[\\/]scripts[\\/]run_benchmark_readiness\.cmd$/);
});

test("benchmark-readiness dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "benchmark-readiness",
    "--input",
    "request.json",
    "--output",
    "out/benchmark-readiness.json",
    "--markdown-output",
    "out/benchmark-readiness.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/benchmark-readiness.json",
    "--markdown-output",
    "out/benchmark-readiness.md",
  ]);
});

test("benchmark-readiness requires an input path", () => {
  const result = runCli(["benchmark-readiness"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for benchmark-readiness/);
});
