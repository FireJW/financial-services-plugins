import { getMaxTurnsFromCliArgs } from "./orchestration-lib.mjs";

const PROFILE_BUDGET_RULES = {
  explore: {
    warningTokens: 1500,
    dangerTokens: 2500,
    warningLines: 180,
    dangerLines: 320,
    warningMaxTurns: 2,
    dangerMaxTurns: 3,
  },
  worker: {
    warningTokens: 3500,
    dangerTokens: 6000,
    warningLines: 420,
    dangerLines: 720,
    warningMaxTurns: 6,
    dangerMaxTurns: 8,
  },
  verifier: {
    warningTokens: 4500,
    dangerTokens: 7500,
    warningLines: 520,
    dangerLines: 860,
    warningMaxTurns: 6,
    dangerMaxTurns: 8,
  },
};

export function buildPromptBudgetReport(options = {}) {
  const profile = options.profile ?? "worker";
  const rules = PROFILE_BUDGET_RULES[profile] ?? PROFILE_BUDGET_RULES.worker;
  const prompt = `${options.prompt ?? ""}`;
  const charCount = prompt.length;
  const lineCount = prompt ? prompt.split(/\r?\n/).length : 0;
  const estimatedTokens = estimateTokensFromChars(charCount);
  const currentMaxTurns =
    Number.isFinite(options.currentMaxTurns)
      ? options.currentMaxTurns
      : getMaxTurnsFromCliArgs(options.cliArgs ?? []);
  const segments = normalizeSegments(options.segments ?? []);

  const riskLevel =
    estimatedTokens >= rules.dangerTokens || lineCount >= rules.dangerLines
      ? "danger"
      : estimatedTokens >= rules.warningTokens || lineCount >= rules.warningLines
        ? "warning"
        : "ok";

  const recommendedMaxTurns =
    riskLevel === "danger"
      ? Math.max(currentMaxTurns ?? 0, rules.dangerMaxTurns)
      : riskLevel === "warning"
        ? Math.max(currentMaxTurns ?? 0, rules.warningMaxTurns)
        : currentMaxTurns ?? null;

  const topSegments = segments
    .sort((left, right) => right.charCount - left.charCount)
    .slice(0, 3)
    .map((segment) => ({
      label: segment.label,
      charCount: segment.charCount,
      estimatedTokens: estimateTokensFromChars(segment.charCount),
      shareOfPrompt: charCount > 0 ? roundNumber(segment.charCount / charCount) : 0,
    }));

  const recommendations = buildBudgetRecommendations({
    profile,
    riskLevel,
    currentMaxTurns,
    recommendedMaxTurns,
    topSegments,
    options,
  });

  return {
    profile,
    charCount,
    lineCount,
    estimatedTokens,
    riskLevel,
    thresholds: {
      warningTokens: rules.warningTokens,
      dangerTokens: rules.dangerTokens,
      warningLines: rules.warningLines,
      dangerLines: rules.dangerLines,
    },
    currentMaxTurns: currentMaxTurns ?? null,
    recommendedMaxTurns,
    topSegments,
    recommendations,
  };
}

export function applyPromptBudgetGuardrails(cliArgs = [], report, options = {}) {
  if (!report) {
    return {
      cliArgs: [...cliArgs],
      adjusted: false,
      reason: null,
    };
  }

  const currentMaxTurns = getMaxTurnsFromCliArgs(cliArgs);
  const allowAutoBump = options.allowAutoBump !== false;
  const shouldBump =
    allowAutoBump &&
    Number.isFinite(report.recommendedMaxTurns) &&
    Number.isFinite(currentMaxTurns) &&
    report.recommendedMaxTurns > currentMaxTurns;

  if (!shouldBump) {
    return {
      cliArgs: [...cliArgs],
      adjusted: false,
      reason: null,
    };
  }

  const nextArgs = [...cliArgs];
  const lastIndex = findLastFlagIndex(nextArgs, "--max-turns");
  nextArgs[lastIndex + 1] = `${report.recommendedMaxTurns}`;

  return {
    cliArgs: nextArgs,
    adjusted: true,
    reason: `prompt budget risk=${report.riskLevel}; auto-raised max-turns from ${currentMaxTurns} to ${report.recommendedMaxTurns}`,
  };
}

export function renderPromptBudgetReport(report) {
  const lines = [];
  lines.push(
    `Prompt budget: risk=${report.riskLevel}, est_tokens=${report.estimatedTokens}, chars=${report.charCount}, lines=${report.lineCount}, max_turns=${report.currentMaxTurns ?? "n/a"}->${report.recommendedMaxTurns ?? "n/a"}`,
  );

  if ((report.topSegments ?? []).length > 0) {
    lines.push("Top prompt segments:");
    for (const segment of report.topSegments) {
      lines.push(
        `- ${segment.label}: chars=${segment.charCount}, est_tokens=${segment.estimatedTokens}, share=${Math.round(segment.shareOfPrompt * 100)}%`,
      );
    }
  }

  if ((report.recommendations ?? []).length > 0) {
    lines.push("Recommendations:");
    for (const recommendation of report.recommendations) {
      lines.push(`- ${recommendation}`);
    }
  }

  return `${lines.join("\n")}\n`;
}

function buildBudgetRecommendations(context) {
  const recommendations = [];

  if (context.riskLevel === "warning" || context.riskLevel === "danger") {
    if (
      Number.isFinite(context.currentMaxTurns) &&
      Number.isFinite(context.recommendedMaxTurns) &&
      context.recommendedMaxTurns > context.currentMaxTurns
    ) {
      recommendations.push(
        `Raise max turns to at least ${context.recommendedMaxTurns} for this ${context.profile} pass.`,
      );
    }
  }

  const dominantSegment = context.topSegments[0];
  if (dominantSegment?.shareOfPrompt >= 0.55) {
    recommendations.push(
      `${dominantSegment.label} dominates the prompt budget; trim or summarize it before adding more context.`,
    );
  }

  if (context.profile === "verifier" && context.options.structuredVerifier !== true) {
    if (context.riskLevel === "danger") {
      recommendations.push(
        "Consider --structured-verifier so wrapper gating depends on JSON instead of markdown parsing for this heavy verifier pass.",
      );
    }
  }

  if ((context.riskLevel === "warning" || context.riskLevel === "danger") && context.profile === "worker") {
    recommendations.push(
      "If the task still grows, split evidence into a smaller context pack before adding more files.",
    );
  }

  return recommendations;
}

function normalizeSegments(segments) {
  return segments
    .map((segment) => ({
      label: `${segment?.label ?? "segment"}`.trim() || "segment",
      charCount: `${segment?.content ?? ""}`.length,
    }))
    .filter((segment) => segment.charCount > 0);
}

function estimateTokensFromChars(charCount) {
  return Math.ceil((charCount ?? 0) / 4);
}

function roundNumber(value) {
  return Number.isFinite(value) ? Math.round(value * 100) / 100 : 0;
}

function findLastFlagIndex(argv, flagName) {
  for (let index = argv.length - 1; index >= 0; index -= 1) {
    if (argv[index] === flagName) {
      return index;
    }
  }

  return -1;
}
