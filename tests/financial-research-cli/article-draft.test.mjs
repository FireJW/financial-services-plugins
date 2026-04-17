import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("article-draft emits stable contract envelope", () => {
  const result = runCli(
    [
      "article-draft",
      "--input",
      "apps/financial-research-cli/examples/article-draft-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "article-draft": {
          status: "ok",
          workflow_kind: "article_draft",
          request: { topic: "Hormuz negotiation realistic offline fixture" },
          source_summary: { topic: "Hormuz negotiation realistic offline fixture", source_kind: "news_index" },
          article_package: {
            title: "Hormuz negotiation realistic offline fixture",
            draft_mode: "balanced",
            draft_thesis: "Indirect contacts continue, but a finalized settlement is still not confirmed.",
            selected_images: [],
            citations: [{ citation_id: "S1" }, { citation_id: "S2" }],
          },
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "article-draft");
  assert.equal(payload.workflow_kind, "article_draft");
  assert.equal(payload.summary.source_kind, "news_index");
  assert.equal(payload.summary.draft_mode, "balanced");
  assert.equal(payload.summary.citation_count, 2);
  assert.match(payload.execution_target.wrapper, /run_article_draft\.cmd$/);
});

test("article-draft dry-run forwards draft tuning options", () => {
  const result = runCli([
    "article-draft",
    "--input",
    "request.json",
    "--title-hint",
    "Quick take",
    "--target-length",
    "1600",
    "--personal-phrase",
    "先看变化",
    "--headline-hook-mode",
    "traffic",
    "--headline-hook-prefix",
    "刚刚",
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
    "1600",
    "--personal-phrase",
    "先看变化",
    "--headline-hook-mode",
    "traffic",
    "--headline-hook-prefixes",
    "刚刚",
  ]);
});

test("article-draft requires an input path", () => {
  const result = runCli(["article-draft"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for article-draft/);
});
