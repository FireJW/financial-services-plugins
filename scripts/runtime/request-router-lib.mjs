import path from "node:path";
import { repoRoot } from "./runtime-report-lib.mjs";

const CORE_PLUGIN_NAMES = Object.freeze([
  "financial-analysis",
  "equity-research",
  "investment-banking",
]);

const CLASSIC_CASE_RULES = Object.freeze([
  {
    id: "latest-event-verification",
    profile: "explore",
    keywords: [
      "latest event",
      "latest verification",
      "verify latest",
      "latest update",
      "最新事件",
      "最新进展",
      "核实最新",
    ],
  },
  {
    id: "x-post-evidence",
    profile: "explore",
    keywords: [
      "x post",
      "x thread",
      "tweet",
      "twitter thread",
      "推文",
      "帖子证据",
      "x帖子",
    ],
  },
  {
    id: "macro-shock-chain-map",
    profile: "worker",
    keywords: [
      "macro shock",
      "shock chain",
      "beneficiaries",
      "losers",
      "war",
      "oil",
      "gas",
      "shipping",
      "tariff",
      "sanction",
      "宏观冲击",
      "冲击链",
      "受益股",
      "受损",
      "战争",
      "油价",
      "天然气",
      "航运",
      "关税",
      "制裁",
    ],
  },
  {
    id: "evidence-to-article",
    profile: "worker",
    keywords: [
      "evidence to article",
      "write article",
      "article draft",
      "evidence-backed article",
      "写成文章",
      "文章草稿",
      "证据转文章",
    ],
  },
  {
    id: "workflow-improvement-loop",
    profile: "worker",
    keywords: [
      "improve workflow",
      "workflow improvement",
      "optimize workflow",
      "改善工作流",
      "优化流程",
      "工作流改进",
    ],
  },
]);

const FEEDBACK_KEYWORDS = Object.freeze([
  "interview",
  "podcast",
  "talk",
  "support ticket",
  "support tickets",
  "customer call",
  "customer calls",
  "social post",
  "social posts",
  "research note",
  "research notes",
  "feedback",
  "workflow",
  "sop",
  "priority brief",
  "cadence",
  "采访",
  "播客",
  "访谈",
  "演讲",
  "用户反馈",
  "客服工单",
  "客户电话",
  "社交媒体",
  "研究笔记",
  "工作流",
  "优先级",
  "节奏",
]);

const A_SHARE_EVENT_KEYWORDS = Object.freeze([
  "a-share",
  "a股",
  "china stocks",
  "china stock",
  "benefit or suffer",
  "benefit",
  "suffer",
  "war",
  "oil",
  "gas",
  "shipping",
  "tariff",
  "sanction",
  "policy shock",
  "headline-driven",
  "earnings-driven",
  "theme",
  "受益",
  "受损",
  "政策冲击",
  "事件驱动",
  "主题炒作",
  "业绩驱动",
]);

export function routeRequest(requestText, options = {}) {
  const text = cleanText(requestText);
  if (!text) {
    throw new Error("routeRequest requires non-empty request text.");
  }

  const requestedPluginDirs = normalizePluginDirs(options.pluginDirs ?? []);
  const rejectedCandidates = [];
  const matchedSignals = [];
  const overrideApplied = {};

  let route = null;

  if (options.routeId) {
    route = buildExplicitRoute(options.routeId, options.classicCaseId);
    overrideApplied.routeId = options.routeId;
    if (options.classicCaseId) {
      overrideApplied.classicCaseId = options.classicCaseId;
    }
  } else if (!options.noAutoRoute) {
    route = detectFeedbackWorkflow(text, matchedSignals, rejectedCandidates);
    if (!route) {
      route = detectClassicCase(text, matchedSignals, rejectedCandidates);
    }
    if (!route) {
      route = detectAShareEventResearch(text, matchedSignals, rejectedCandidates);
    }
  }

  if (!route) {
    route = buildFallbackRoute();
  }

  if (options.profile) {
    route.profile = options.profile;
    overrideApplied.profile = options.profile;
  }

  const pluginDirs =
    requestedPluginDirs.length > 0
      ? requestedPluginDirs
      : getDefaultPluginDirsForRoute(route.routeId, route.classicCaseId);
  if (requestedPluginDirs.length > 0) {
    overrideApplied.pluginDirs = [...requestedPluginDirs];
  }

  const plan = {
    requestText: text,
    routeId: route.routeId,
    classicCaseId: route.classicCaseId ?? null,
    confidence: route.confidence,
    matchedSignals: [...matchedSignals],
    rejectedCandidates,
    profile: route.profile,
    pluginDirs,
    nativeWorkflow: route.nativeWorkflow,
    notes: route.notes,
    overrideApplied,
    nextInvocation: buildNextInvocationPlan(route.profile, pluginDirs),
  };

  return plan;
}

export function renderRoutePlan(plan, options = {}) {
  const lines = [];
  lines.push(`Route: ${plan.routeId}`);
  if (plan.classicCaseId) {
    lines.push(`Classic case: ${plan.classicCaseId}`);
  }
  lines.push(`Confidence: ${plan.confidence}`);
  lines.push(`Profile: ${plan.profile}`);
  lines.push("Plugin dirs:");
  for (const pluginDir of plan.pluginDirs) {
    lines.push(`- ${pluginDir}`);
  }
  lines.push("Native workflow:");
  for (const item of plan.nativeWorkflow) {
    lines.push(`- ${item}`);
  }
  lines.push(`Next command: ${plan.nextInvocation.displayCommand}`);

  if (options.trace) {
    lines.push("Matched signals:");
    for (const signal of plan.matchedSignals) {
      lines.push(`- ${signal.kind}: ${signal.value}`);
    }

    if (plan.rejectedCandidates.length > 0) {
      lines.push("Rejected candidates:");
      for (const candidate of plan.rejectedCandidates) {
        lines.push(`- ${candidate.routeId}: ${candidate.reason}`);
      }
    }

    const overrideKeys = Object.keys(plan.overrideApplied);
    if (overrideKeys.length > 0) {
      lines.push("Overrides:");
      for (const key of overrideKeys) {
        lines.push(`- ${key}: ${JSON.stringify(plan.overrideApplied[key])}`);
      }
    }
  }

  return `${lines.join("\n")}\n`;
}

function buildExplicitRoute(routeId, classicCaseId) {
  if (routeId === "classic_case") {
    const caseRule = findClassicCaseRule(classicCaseId);
    if (!caseRule) {
      throw new Error(`Unknown classic case override: ${classicCaseId ?? "<missing>"}`);
    }

    return buildClassicCaseRoute(caseRule, "high");
  }

  if (routeId === "feedback_workflow") {
    return buildFeedbackWorkflowRoute("high");
  }

  if (routeId === "a_share_event_research") {
    return buildAShareEventResearchRoute("high");
  }

  if (routeId === "fallback_search") {
    return buildFallbackRoute();
  }

  throw new Error(`Unknown route override: ${routeId}`);
}

function detectFeedbackWorkflow(text, matchedSignals, rejectedCandidates) {
  const hits = FEEDBACK_KEYWORDS.filter((keyword) => text.includes(keyword));
  const hasWorkflowGoal =
    text.includes("workflow") ||
    text.includes("sop") ||
    text.includes("priorit") ||
    text.includes("cadence") ||
    text.includes("工作流") ||
    text.includes("优先级") ||
    text.includes("节奏");

  if (hits.length >= 2 && hasWorkflowGoal) {
    for (const hit of hits.slice(0, 4)) {
      matchedSignals.push({
        kind: "feedback_keyword",
        value: hit,
      });
    }
    return buildFeedbackWorkflowRoute(hits.length >= 3 ? "high" : "medium");
  }

  if (hits.length > 0) {
    rejectedCandidates.push({
      routeId: "feedback_workflow",
      reason: "Feedback-like terms matched, but the request did not clearly ask for a workflow, SOP, priorities brief, or cadence output.",
    });
  }

  return null;
}

function detectClassicCase(text, matchedSignals, rejectedCandidates) {
  const rankedCases = CLASSIC_CASE_RULES.map((rule) => ({
    rule,
    hits: rule.keywords.filter((keyword) => text.includes(keyword)),
  }))
    .filter((entry) => entry.hits.length > 0)
    .sort((left, right) => right.hits.length - left.hits.length);

  if (rankedCases.length === 0) {
    return null;
  }

  const [winner, ...rest] = rankedCases;
  for (const hit of winner.hits.slice(0, 4)) {
    matchedSignals.push({
      kind: "classic_case_keyword",
      value: `${winner.rule.id}:${hit}`,
    });
  }

  for (const entry of rest.slice(0, 3)) {
    rejectedCandidates.push({
      routeId: "classic_case",
      reason: `Matched ${entry.rule.id}, but ${winner.rule.id} had more specific signals.`,
    });
  }

  const confidence = winner.hits.length >= 2 ? "high" : "medium";
  return buildClassicCaseRoute(winner.rule, confidence);
}

function detectAShareEventResearch(text, matchedSignals, rejectedCandidates) {
  const hits = A_SHARE_EVENT_KEYWORDS.filter((keyword) => text.includes(keyword));
  if (hits.length < 2) {
    if (hits.length > 0) {
      rejectedCandidates.push({
        routeId: "a_share_event_research",
        reason: "A-share event research terms partially matched, but not strongly enough to outrank a more specific route.",
      });
    }
    return null;
  }

  for (const hit of hits.slice(0, 4)) {
    matchedSignals.push({
      kind: "a_share_keyword",
      value: hit,
    });
  }

  return buildAShareEventResearchRoute(hits.length >= 3 ? "high" : "medium");
}

function buildFeedbackWorkflowRoute(confidence) {
  return {
    routeId: "feedback_workflow",
    classicCaseId: null,
    profile: "worker",
    confidence,
    nativeWorkflow: [
      "financial-analysis/commands/feedback-workflow.md",
      "financial-analysis/skills/feedback-iteration-workflow/SKILL.md",
      "financial-analysis/skills/autoresearch-info-index/SKILL.md (when freshness matters)",
    ],
    notes: [
      "Separate direct quote, direct-ish, summary, and inference only.",
      "Keep exact as-of dates in the output.",
    ],
  };
}

function buildClassicCaseRoute(rule, confidence) {
  return {
    routeId: "classic_case",
    classicCaseId: rule.id,
    profile: rule.profile,
    confidence,
    nativeWorkflow: [
      "financial-analysis/skills/classic-case-router/SKILL.md",
      `financial-analysis/skills/classic-case-router/references/${rule.id}.md`,
    ],
    notes: [
      "State which classic case matched before doing the main work.",
      "Only improvise after the case path has been checked.",
    ],
  };
}

function buildAShareEventResearchRoute(confidence) {
  return {
    routeId: "a_share_event_research",
    classicCaseId: null,
    profile: "worker",
    confidence,
    nativeWorkflow: [
      "financial-analysis/skills/autoresearch-info-index/SKILL.md",
      "financial-analysis/skills/macro-shock-analysis/SKILL.md",
      "equity-research/commands/sector.md",
      "equity-research/commands/earnings.md",
      "equity-research/commands/model-update.md",
      "equity-research/commands/screen.md",
    ],
    notes: [
      "Anchor time-sensitive claims to exact dates.",
      "Separate confirmed, likely, and inference only.",
    ],
  };
}

function buildFallbackRoute() {
  return {
    routeId: "fallback_search",
    classicCaseId: null,
    profile: "explore",
    confidence: "low",
    nativeWorkflow: [
      "scripts/runtime/run-task-profile.mjs --profile explore",
    ],
    notes: [
      "Use explore for cheap reconnaissance before escalating to worker.",
    ],
  };
}

function findClassicCaseRule(caseId) {
  return CLASSIC_CASE_RULES.find((rule) => rule.id === caseId) ?? null;
}

function getDefaultPluginDirsForRoute(routeId, classicCaseId) {
  const pluginNames = [];

  if (routeId === "feedback_workflow") {
    pluginNames.push("financial-analysis");
  } else if (routeId === "classic_case") {
    pluginNames.push("financial-analysis");
    if (classicCaseId === "macro-shock-chain-map") {
      pluginNames.push("equity-research");
    }
  } else if (routeId === "a_share_event_research") {
    pluginNames.push("financial-analysis", "equity-research");
  } else {
    pluginNames.push(...CORE_PLUGIN_NAMES);
  }

  return normalizePluginDirs(pluginNames);
}

function buildNextInvocationPlan(profile, pluginDirs) {
  const args = ["node", "scripts/runtime/run-task-profile.mjs", "--profile", profile];
  for (const pluginDir of pluginDirs) {
    args.push("--plugin-dir", pluginDir);
  }
  args.push("--dry-run", "--json");

  return {
    profile,
    pluginDirs,
    command: "node",
    scriptPath: path.join("scripts", "runtime", "run-task-profile.mjs"),
    args: args.slice(1),
    displayCommand: args.join(" "),
  };
}

function normalizePluginDirs(pluginDirs) {
  return pluginDirs
    .map((pluginDir) =>
      path.isAbsolute(pluginDir) ? pluginDir : path.join(repoRoot, pluginDir),
    )
    .filter((pluginDir, index, values) => values.indexOf(pluginDir) === index);
}

function cleanText(text) {
  return String(text ?? "")
    .trim()
    .toLowerCase();
}
