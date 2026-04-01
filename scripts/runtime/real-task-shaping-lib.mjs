import {
  buildWorkerPrompt,
} from "./orchestration-lib.mjs";
import {
  buildPromptBudgetReport,
  renderPromptBudgetReport,
} from "./runtime-prompt-budget-lib.mjs";

export const REAL_TASK_SHAPING_PLAN_SCHEMA_VERSION = "real-task-shaping-plan-v1";

export function buildRealTaskShapingPlan(options = {}) {
  const contextItems = normalizeContextItems(options.contextItems ?? []);
  const workerPrompt = buildWorkerPrompt({
    task: options.task,
    intentMarkdown: options.intentMarkdown,
    nowMarkdown: options.nowMarkdown,
    contextItems,
  });
  const workerPromptBudgetReport = buildPromptBudgetReport({
    profile: "worker",
    prompt: workerPrompt,
    cliArgs: options.cliArgs ?? ["--print", "--max-turns", "4", "--output-format", "text"],
    segments: [
      { label: "Task", content: options.task },
      { label: "Intent", content: options.intentMarkdown },
      { label: "NOW", content: options.nowMarkdown },
      ...contextItems.map((item) => ({ label: item.label, content: item.content })),
    ],
  });

  const routeId = options.routePlan?.routeId ?? "unknown";
  const dominantSegment = workerPromptBudgetReport.topSegments[0]?.label ?? null;
  const riskLevel = workerPromptBudgetReport.riskLevel;
  const contextFileCount = contextItems.length;
  const totalContextChars = contextItems.reduce(
    (sum, item) => sum + `${item.content ?? ""}`.length,
    0,
  );

  let strategy = "direct_run";
  const recommendedActions = [];
  const routeSpecificNotes = [];

  if (riskLevel === "warning") {
    strategy = contextFileCount > 1 ? "trim_context_pack" : "summarize_evidence_first";
    recommendedActions.push(
      "Keep only the highest-signal context for the first worker pass.",
      "Write a smaller evidence summary before adding more files to the worker prompt.",
    );
  }

  if (riskLevel === "danger") {
    strategy = contextFileCount > 1 ? "split_context_pack" : "summarize_evidence_first";
    recommendedActions.push(
      "Do not run the full evidence pack directly through the first worker pass.",
      "Create a smaller evidence summary or chunk the context pack before rerunning.",
      "Use the first worker pass to normalize evidence, then run a second worker pass for synthesis.",
    );
  }

  if (dominantSegment && workerPromptBudgetReport.topSegments[0]?.shareOfPrompt >= 0.55) {
    recommendedActions.push(
      `${dominantSegment} is dominating the prompt budget; reduce that segment before adding anything else.`,
    );
  }

  if (contextFileCount > 1) {
    recommendedActions.push(
      "Sequence context files in passes instead of feeding every evidence file into the same worker prompt.",
    );
  }

  if (routeId === "feedback_workflow") {
    routeSpecificNotes.push(
      "Separate direct quote, direct-ish, summary, and inference only before the first synthesis pass.",
    );
  }

  if (routeId === "classic_case") {
    routeSpecificNotes.push(
      "Anchor the first pass to the matched classic case before broadening context.",
    );
  }

  if (routeId === "a_share_event_research") {
    routeSpecificNotes.push(
      "Classify company chain position before adding valuation or trading overlays.",
    );
  }

  const plan = {
    schemaVersion: REAL_TASK_SHAPING_PLAN_SCHEMA_VERSION,
    generatedAt: new Date().toISOString(),
    routeId,
    riskLevel,
    strategy,
    needsOperatorAttention: riskLevel === "danger",
    contextFileCount,
    totalContextChars,
    dominantSegment,
    workerPromptBudgetReport,
    recommendedActions: dedupeStrings([
      ...workerPromptBudgetReport.recommendations,
      ...recommendedActions,
    ]),
    routeSpecificNotes: dedupeStrings(routeSpecificNotes),
    suggestedNextStep:
      riskLevel === "danger"
        ? "Summarize or split the evidence pack before running the main worker pass."
        : riskLevel === "warning"
          ? "Trim the evidence pack or accept a slower worker pass with the current budget guardrails."
          : "Run the direct worker -> verifier flow.",
  };

  return plan;
}

export function renderRealTaskShapingPlan(plan) {
  const lines = [];
  lines.push("Real Task Shaping Plan");
  lines.push(`- route: ${plan.routeId}`);
  lines.push(`- risk: ${plan.riskLevel}`);
  lines.push(`- strategy: ${plan.strategy}`);
  lines.push(`- needs_operator_attention: ${plan.needsOperatorAttention}`);
  lines.push(`- context_files: ${plan.contextFileCount}`);
  lines.push(`- total_context_chars: ${plan.totalContextChars}`);
  if (plan.dominantSegment) {
    lines.push(`- dominant_segment: ${plan.dominantSegment}`);
  }
  lines.push("");
  lines.push("Budget Summary");
  lines.push(renderPromptBudgetReport(plan.workerPromptBudgetReport).trimEnd());

  if ((plan.recommendedActions ?? []).length > 0) {
    lines.push("");
    lines.push("Recommended Actions");
    for (const action of plan.recommendedActions) {
      lines.push(`- ${action}`);
    }
  }

  if ((plan.routeSpecificNotes ?? []).length > 0) {
    lines.push("");
    lines.push("Route-Specific Notes");
    for (const note of plan.routeSpecificNotes) {
      lines.push(`- ${note}`);
    }
  }

  lines.push("");
  lines.push("Suggested Next Step");
  lines.push(`- ${plan.suggestedNextStep}`);

  return `${lines.join("\n")}\n`;
}

function normalizeContextItems(contextItems) {
  return contextItems.map((item, index) => ({
    label: `${item?.label ?? `Context ${index + 1}`}`.trim() || `Context ${index + 1}`,
    content: `${item?.content ?? ""}`,
  }));
}

function dedupeStrings(items) {
  return [...new Set(items.filter(Boolean).map((item) => `${item}`.trim()).filter(Boolean))];
}
