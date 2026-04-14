import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("article-brief emits stable contract envelope", () => {
  const result = runCli(
    [
      "article-brief",
      "--input",
      "apps/financial-research-cli/examples/article-brief-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "article-brief": {
          status: "ok",
          workflow_kind: "article_brief",
          request: { topic: "Hormuz negotiation realistic offline fixture" },
          source_summary: { topic: "Hormuz negotiation realistic offline fixture", source_kind: "news_index" },
          supporting_citations: [{ citation_id: "S1" }, { citation_id: "S2" }],
          analysis_brief: {
            canonical_facts: [{ claim_text: "Indirect contacts continue." }],
            not_proven: [{ claim_text: "A finalized settlement exists." }],
            story_angles: [{ angle: "Negotiation vs settlement boundary" }],
            recommended_thesis: "Indirect contacts continue, but a finalized settlement is still not confirmed.",
          },
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "article-brief");
  assert.equal(payload.workflow_kind, "article_brief");
  assert.equal(payload.summary.source_kind, "news_index");
  assert.equal(payload.summary.canonical_fact_count, 1);
  assert.equal(payload.summary.supporting_citation_count, 2);
  assert.match(payload.execution_target.wrapper, /run_article_brief\.cmd$/);
});

test("article-brief dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "article-brief",
    "--input",
    "request.json",
    "--output",
    "out/article-brief.json",
    "--markdown-output",
    "out/article-brief.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output",
    "out/article-brief.json",
    "--markdown-output",
    "out/article-brief.md",
  ]);
});

test("article-brief requires an input path", () => {
  const result = runCli(["article-brief"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for article-brief/);
});
