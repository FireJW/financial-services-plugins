import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("last30days-bridge emits stable contract envelope", () => {
  const result = runCli(
    [
      "last30days-bridge",
      "--input",
      "apps/financial-research-cli/examples/last30days-bridge-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "last30days-bridge": {
          status: "ok",
          workflow_kind: "last30days_bridge",
          request: {
            topic: "Hormuz escalation and regional mediation watch",
            result_path: "financial-analysis/skills/autoresearch-info-index/examples/last30days-bridge-input.json",
          },
          import_summary: {
            raw_item_count: 4,
            imported_candidate_count: 4,
            batch_labels: ["findings", "web", "polymarket"],
            blocked_count: 1,
            with_artifacts: 1,
          },
          retrieval_result: {
            observations: [
              {
                url: "https://x.com/sentdefender/status/2036153038906196133",
              },
            ],
          },
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "last30days-bridge");
  assert.equal(payload.workflow_kind, "last30days_bridge");
  assert.equal(payload.summary.imported_count, 4);
  assert.equal(payload.summary.batch_label_count, 3);
  assert.equal(payload.summary.with_artifacts, 1);
  assert.match(payload.execution_target.wrapper, /run_last30days_bridge\.cmd$/);
});

test("last30days-bridge dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "last30days-bridge",
    "--input",
    "request.json",
    "--output",
    "out/last30days-bridge.json",
    "--markdown-output",
    "out/last30days-bridge.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/last30days-bridge.json",
    "--markdown-output",
    "out/last30days-bridge.md",
  ]);
});

test("last30days-bridge requires an input path", () => {
  const result = runCli(["last30days-bridge"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for last30days-bridge/);
});
