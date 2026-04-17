import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("article-workflow emits stable contract envelope", () => {
  const result = runCli(
    [
      "article-workflow",
      "--input",
      "financial-analysis/skills/autoresearch-info-index/examples/news-index-realistic-offline-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "article-workflow": {
          status: "ok",
          workflow_kind: "article_workflow",
          topic: "Hormuz negotiation realistic offline fixture",
          publication_readiness: "ready",
          source_stage: { source_kind: "news_index" },
          final_stage: { quality_gate: "pass" },
          final_article_result_path: "out/final-article-result.json",
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "ready" },
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "article-workflow");
  assert.equal(payload.workflow_kind, "article_workflow");
  assert.equal(payload.summary.topic, "Hormuz negotiation realistic offline fixture");
  assert.equal(payload.summary.source_kind, "news_index");
  assert.equal(payload.summary.quality_gate, "pass");
  assert.match(payload.execution_target.wrapper, /run_article_workflow\.cmd$/);
});

test("article-workflow dry-run forwards article workflow tuning options", () => {
  const result = runCli([
    "article-workflow",
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

test("article-workflow requires an input path", () => {
  const result = runCli(["article-workflow"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for article-workflow/);
});
