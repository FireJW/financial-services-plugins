import test from "node:test";
import assert from "node:assert/strict";
import { buildRealTaskShapingPlan } from "../../scripts/runtime/real-task-shaping-lib.mjs";

test("real-task shaping plan stays direct for small feedback workflow tasks", () => {
  const plan = buildRealTaskShapingPlan({
    routePlan: { routeId: "feedback_workflow" },
    task: "Turn Jenny Wen feedback evidence into a workflow.",
    intentMarkdown: "## User Intent\n- Build the workflow.\n\n## Hard Constraints\n- Keep quote tiers honest.\n\n## Non-goals\n- None.\n",
    nowMarkdown: "## Goal\n- Ship.\n",
    contextItems: [
      {
        label: "Context: Route guidance",
        content: "Use the feedback workflow route.",
      },
      {
        label: "Context: Evidence",
        content: "Direct-ish signal.\nSummary signal.\nInference only signal.",
      },
    ],
  });

  assert.equal(plan.schemaVersion, "real-task-shaping-plan-v1");
  assert.equal(plan.riskLevel, "ok");
  assert.equal(plan.strategy, "direct_run");
  assert.ok(
    plan.routeSpecificNotes.some((note) => note.includes("direct quote")),
    JSON.stringify(plan, null, 2),
  );
});

test("real-task shaping plan recommends splitting oversized evidence packs", () => {
  const hugeEvidence = "Evidence line.\n".repeat(2500);
  const plan = buildRealTaskShapingPlan({
    routePlan: { routeId: "a_share_event_research" },
    task: "Compare two A-share names under a macro shock.",
    intentMarkdown: "## User Intent\n- Compare the names.\n\n## Hard Constraints\n- Anchor dates.\n\n## Non-goals\n- None.\n",
    nowMarkdown: "## Goal\n- Finish the first pass.\n",
    contextItems: [
      {
        label: "Context: Evidence pack A",
        content: hugeEvidence,
      },
      {
        label: "Context: Evidence pack B",
        content: hugeEvidence,
      },
    ],
  });

  assert.equal(plan.riskLevel, "danger");
  assert.ok(
    plan.strategy === "split_context_pack" ||
      plan.strategy === "summarize_evidence_first",
    JSON.stringify(plan, null, 2),
  );
  assert.equal(plan.needsOperatorAttention, true);
  assert.ok(
    plan.recommendedActions.some((action) => action.includes("smaller evidence summary")) ||
      plan.recommendedActions.some((action) => action.includes("chunk the context pack")),
    JSON.stringify(plan, null, 2),
  );
  assert.ok(
    plan.routeSpecificNotes.some((note) => note.includes("chain position")),
    JSON.stringify(plan, null, 2),
  );
});
