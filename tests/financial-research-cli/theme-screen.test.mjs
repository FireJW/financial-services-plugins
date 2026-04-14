import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("theme-screen emits stable contract envelope", () => {
  const result = runCli(
    [
      "theme-screen",
      "--input",
      "financial-analysis/skills/autoresearch-info-index/examples/hot-topic-reddit-multi-post-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "theme-screen": {
          status: "ok",
          workflow_kind: "hot_topic_discovery",
          ranked_topics: [{ title: "NVIDIA chatter", max_heat_score: 92.5 }],
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "ready" },
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "theme-screen");
  assert.equal(payload.workflow_kind, "hot_topic_discovery");
  assert.equal(payload.summary.topic_count, 1);
  assert.equal(payload.summary.top_topic, "NVIDIA chatter");
});

test("theme-screen can run from direct topic without input", () => {
  const result = runCli([
    "theme-screen",
    "--topic",
    "AI agent frontier",
    "--source",
    "google-news",
    "--source",
    "agent-reach:reddit",
    "--top-n",
    "3",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "--topic",
    "AI agent frontier",
    "--sources",
    "google-news",
    "agent-reach:reddit",
    "--top-n",
    "3",
  ]);
});

test("theme-screen requires either input or topic", () => {
  const result = runCli(["theme-screen"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /requires either --input <path> or --topic <text>/);
});
