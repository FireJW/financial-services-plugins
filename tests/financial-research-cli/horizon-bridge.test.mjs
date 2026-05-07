import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("horizon-bridge emits stable contract envelope", () => {
  const result = runCli(
    [
      "horizon-bridge",
      "--input",
      "financial-analysis/skills/autoresearch-info-index/examples/horizon-bridge-request.template.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "horizon-bridge": {
          status: "ok",
          workflow_kind: "horizon_bridge",
          request: {
            topic: "AI infrastructure upstream discovery",
          },
          import_summary: {
            payload_source: "inline_result",
            raw_item_count: 2,
            imported_candidate_count: 2,
            channel_counts: { shadow: 2 },
            access_mode_counts: { local_mcp: 2 },
          },
          retrieval_result: {
            observations: [
              {
                origin: "horizon",
                channel: "shadow",
                access_mode: "local_mcp",
                url: "https://example.com/horizon-ai-power",
              },
            ],
          },
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "ready" },
          completion_check_path: "out/horizon-bridge-completion-check.json",
          operator_summary_path: "out/horizon-bridge-operator-summary.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "horizon-bridge");
  assert.equal(payload.workflow_kind, "horizon_bridge");
  assert.equal(payload.summary.imported_count, 2);
  assert.equal(payload.summary.payload_source, "inline_result");
  assert.equal(payload.summary.first_observation_origin, "horizon");
  assert.equal(payload.summary.first_observation_channel, "shadow");
  assert.equal(payload.summary.first_observation_access_mode, "local_mcp");
  assert.match(payload.execution_target.wrapper, /run_horizon_bridge\.cmd$/);
});

test("horizon-bridge dry-run shows saved-payload execution plan", () => {
  const result = runCli([
    "horizon-bridge",
    "--input",
    "request.json",
    "--output",
    "out/horizon-bridge.json",
    "--markdown-output",
    "out/horizon-bridge.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/horizon-bridge.json",
    "--markdown-output",
    "out/horizon-bridge.md",
  ]);
});

test("horizon-bridge requires an input path", () => {
  const result = runCli(["horizon-bridge"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for horizon-bridge/);
});
