import test from "node:test";
import assert from "node:assert/strict";
import {
  applyPromptBudgetGuardrails,
  buildPromptBudgetReport,
  renderPromptBudgetReport,
} from "../../scripts/runtime/runtime-prompt-budget-lib.mjs";

test("prompt budget report flags large verifier prompts and recommends structured mode", () => {
  const workerOutput = "## Conclusion\n\n- Evidence.\n".repeat(900);
  const report = buildPromptBudgetReport({
    profile: "verifier",
    prompt: workerOutput,
    cliArgs: ["--print", "--max-turns", "4", "--output-format", "text"],
    structuredVerifier: false,
    segments: [
      { label: "Worker output", content: workerOutput },
      { label: "Original task", content: "Summarize Jenny Wen workflow." },
    ],
  });

  assert.equal(report.riskLevel, "danger");
  assert.equal(report.recommendedMaxTurns, 8);
  assert.equal(report.topSegments[0].label, "Worker output");
  assert.ok(
    report.recommendations.some((item) => item.includes("--structured-verifier")),
    JSON.stringify(report, null, 2),
  );
});

test("prompt budget guardrails auto-raise max turns when no explicit override is present", () => {
  const report = buildPromptBudgetReport({
    profile: "worker",
    prompt: "Context block\n".repeat(1800),
    cliArgs: ["--print", "--max-turns", "4", "--output-format", "text"],
    segments: [{ label: "Context", content: "Context block\n".repeat(1800) }],
  });

  const guardrail = applyPromptBudgetGuardrails(
    ["--print", "--max-turns", "4", "--output-format", "text"],
    report,
    { allowAutoBump: true },
  );

  assert.equal(guardrail.adjusted, true, JSON.stringify({ report, guardrail }, null, 2));
  assert.deepEqual(
    guardrail.cliArgs,
    ["--print", "--max-turns", "8", "--output-format", "text"],
  );
  assert.match(guardrail.reason ?? "", /auto-raised max-turns/);
});

test("prompt budget report renders a readable summary", () => {
  const report = buildPromptBudgetReport({
    profile: "worker",
    prompt: "Task\n".repeat(100),
    cliArgs: ["--print", "--max-turns", "4", "--output-format", "text"],
    segments: [{ label: "Task", content: "Task\n".repeat(100) }],
  });

  const rendered = renderPromptBudgetReport(report);

  assert.match(rendered, /Prompt budget: risk=/);
  assert.match(rendered, /Top prompt segments:/);
});
