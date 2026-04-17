import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("earnings-update emits stable contract envelope", () => {
  const result = runCli(
    [
      "earnings-update",
      "--input",
      "financial-analysis/skills/autoresearch-info-index/examples/news-index-realistic-offline-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "earnings-update": {
          status: "ok",
          workflow_kind: "article_workflow",
          publication_readiness: "ready",
          source_stage: { source_kind: "news_index" },
          final_stage: { quality_gate: "pass" },
          final_article_result_path: "out/final-article-result.json",
          operator_summary_path: "out/operator-summary.json",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "earnings-update");
  assert.equal(payload.workflow_kind, "article_workflow");
  assert.equal(payload.summary.source_kind, "news_index");
  assert.equal(payload.summary.quality_gate, "pass");
  assert.match(payload.execution_target.wrapper, /run_article_workflow\.cmd$/);
});

test("earnings-update dry-run forwards article workflow tuning options", () => {
  const result = runCli([
    "earnings-update",
    "--input",
    "request.json",
    "--title-hint",
    "Quick take",
    "--target-length",
    "1800",
    "--personal-phrase",
    "先看变化",
    "--personal-phrase",
    "真正的分水岭",
    "--headline-hook-mode",
    "traffic",
    "--headline-hook-prefix",
    "刚刚",
    "--headline-hook-prefix",
    "突发",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--title-hint",
    "Quick take",
    "--target-length",
    "1800",
    "--personal-phrase",
    "先看变化",
    "--personal-phrase",
    "真正的分水岭",
    "--headline-hook-mode",
    "traffic",
    "--headline-hook-prefixes",
    "刚刚",
    "突发",
  ]);
});

test("earnings-update requires an input path", () => {
  const result = runCli(["earnings-update"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for earnings-update/);
});
