import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("agent-reach-bridge emits stable contract envelope", () => {
  const result = runCli(
    [
      "agent-reach-bridge",
      "--input",
      "apps/financial-research-cli/examples/agent-reach-bridge-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "agent-reach-bridge": {
          status: "ok",
          workflow_kind: "agent_reach_bridge",
          topic: "Huawei AI chip orders",
          channels_attempted: ["github", "youtube"],
          channels_succeeded: ["github", "youtube"],
          channels_failed: [],
          observations_imported: 2,
          observations_skipped_duplicate: 0,
          retrieval_result: {
            observations: [
              {
                url: "https://github.com/example/huawei-chip-watch",
              },
            ],
          },
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "ready" },
          completion_check_path: "out/agent-reach-bridge-completion-check.json",
          operator_summary_path: "out/agent-reach-bridge-operator-summary.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "agent-reach-bridge");
  assert.equal(payload.workflow_kind, "agent_reach_bridge");
  assert.equal(payload.summary.channel_success_count, 2);
  assert.equal(payload.summary.observations_imported, 2);
  assert.match(payload.execution_target.wrapper, /run_agent_reach_bridge\.cmd$/);
});

test("agent-reach-bridge dry-run supports direct channel overrides", () => {
  const result = runCli([
    "agent-reach-bridge",
    "--file",
    "payload.json",
    "--topic",
    "AI agent frontier",
    "--channel",
    "github",
    "--channel",
    "youtube",
    "--pseudo-home",
    "D:/agent-reach-home",
    "--timeout-per-channel",
    "15",
    "--max-results-per-channel",
    "4",
    "--output",
    "out/agent-reach-bridge.json",
    "--markdown-output",
    "out/agent-reach-bridge.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "--file",
    "payload.json",
    "--topic",
    "AI agent frontier",
    "--channels",
    "github",
    "youtube",
    "--pseudo-home",
    "D:/agent-reach-home",
    "--timeout-per-channel",
    "15",
    "--max-results-per-channel",
    "4",
    "--output",
    "out/agent-reach-bridge.json",
    "--markdown-output",
    "out/agent-reach-bridge.md",
  ]);
});

test("agent-reach-bridge requires input, topic, or file", () => {
  const result = runCli(["agent-reach-bridge"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /agent-reach-bridge requires --input <path>, --topic <text>, or --file <path>/);
});
