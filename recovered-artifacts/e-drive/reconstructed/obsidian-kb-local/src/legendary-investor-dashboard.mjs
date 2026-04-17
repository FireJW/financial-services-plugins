import fs from "node:fs";
import path from "node:path";
import { findWikiNotes } from "./compile-pipeline.mjs";
import { normalizeChecklistState } from "./legendary-investor-checklist.mjs";

export function buildLegendaryInvestorDashboard(config, options = {}) {
  const runPath = options.runPath || path.join(config.projectRoot, "handoff", "legendary-investor-last-run.json");
  const checklistStatePath =
    options.checklistStatePath ||
    path.join(config.projectRoot, "handoff", "legendary-investor-checklist-state.json");
  const decisionJsonPath =
    options.decisionJsonPath ||
    path.join(config.projectRoot, "handoff", "legendary-investor-last-decision.json");
  const reviewJsonPath =
    options.reviewJsonPath ||
    path.join(config.projectRoot, "handoff", "legendary-investor-last-review.json");

  const runData = readJsonIfExists(runPath);
  const checklistState = normalizeChecklistState(readJsonIfExists(checklistStatePath));
  const decisionData = readJsonIfExists(decisionJsonPath);
  const reviewData = readJsonIfExists(reviewJsonPath);
  const wikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {});
  const latestDecision = findLatestLegendaryNote(wikiNotes, "Legendary-Investor-Decision-");
  const latestReview = findLatestLegendaryNote(wikiNotes, "Legendary-Investor-Review-");
  const checklistProgress = buildChecklistProgress(runData, checklistState);

  return {
    generatedAt: options.generatedAt || new Date().toISOString(),
    runPath,
    checklistStatePath,
    decisionJsonPath,
    reviewJsonPath,
    runData,
    checklistState,
    decisionData,
    reviewData,
    checklistProgress,
    latestDecision,
    latestReview
  };
}

export function renderLegendaryInvestorDashboard(report) {
  const runData = report.runData || {};
  const summary = runData.summary || {};
  const committee = runData.committee || {};
  const verdict = committee.verdict || {};
  const lines = [
    "# Legendary Investor Dashboard",
    "",
    `- generated_at: ${report.generatedAt}`,
    `- run_json: ${report.runPath}`,
    `- checklist_state: ${report.checklistStatePath}`,
    `- decision_json: ${report.decisionJsonPath}`,
    `- review_json: ${report.reviewJsonPath}`,
    `- playbook: ${runData.playbook?.label || "(missing)"}`,
    `- single_mentor: ${summary.singleMentor || "(missing)"}`,
    ""
  ];

  if (summary.primaryLeg || summary.hedgeLeg || summary.confirmLeg) {
    lines.push("## Current Structure");
    lines.push(`- primary: ${summary.primaryLeg || "(missing)"}`);
    lines.push(`- hedge: ${summary.hedgeLeg || "(missing)"}`);
    lines.push(`- confirm: ${summary.confirmLeg || "(missing)"}`);
    lines.push(`- default_structure: ${verdict.defaultStructure || "(missing)"}`);
    lines.push(`- upgrade_path: ${verdict.upgradePath || "(missing)"}`);
    lines.push(`- downgrade_sequence: ${verdict.downgradeSequence || "(missing)"}`);
    lines.push("");
  }

  lines.push("## Checklist Progress");
  lines.push(`- completed: ${report.checklistProgress.completed}/${report.checklistProgress.total}`);
  if (report.checklistProgress.checkedItems.length > 0) {
    for (const item of report.checklistProgress.checkedItems) {
      lines.push(`- [x] ${item.label}${item.note ? ` | note=${item.note}` : ""}`);
    }
  } else {
    lines.push("- (none)");
  }
  lines.push("");

  lines.push("## Latest Verdicts");
  lines.push(`- decision_verdict: ${report.decisionData?.verdict || "(missing)"}`);
  lines.push(`- review_verdict: ${report.reviewData?.verdict || "(missing)"}`);
  lines.push("");

  lines.push("## Latest Notes");
  lines.push(`- decision: ${formatNoteRef(report.latestDecision)}`);
  lines.push(`- review: ${formatNoteRef(report.latestReview)}`);
  lines.push("");

  return lines.join("\n").trim();
}

function buildChecklistProgress(runData, checklistState) {
  const allIds = [
    ...inferChecklistIds(runData, "preopen"),
    ...inferChecklistIds(runData, "committee"),
    ...inferChecklistIds(runData, "trade_cards")
  ];
  const checkedItems = [];

  for (const id of allIds) {
    const state = checklistState.items[id];
    if (!state?.checked) {
      continue;
    }
    checkedItems.push({
      id,
      label: inferChecklistLabel(runData, id),
      note: state.note || ""
    });
  }

  return {
    total: allIds.length,
    completed: checkedItems.length,
    checkedItems
  };
}

function inferChecklistIds(runData, category) {
  switch (category) {
    case "preopen":
      if (runData.playbook?.key === "valuation_quality") {
        return ["quality", "capital_allocation", "odds", "holding_intent"];
      }
      if (runData.playbook?.key === "supply_demand_cycle") {
        return ["price_hike", "supply_shortage", "high_utilization", "primary_leg", "confirm_leg"];
      }
      if (runData.playbook?.key === "macro_reflexive") {
        return ["liquidity", "cross_asset", "macro_break"];
      }
      return ["event_status", "primary_leg", "hedge_leg", "confirm_leg"];
    case "committee":
      return ["default_structure", "upgrade_path", "downgrade_sequence", "do_not_do"];
    case "trade_cards":
      return Object.values(runData.tradeCards || {}).map((card) => `${card.role}_${card.leg}`);
    default:
      return [];
  }
}

function inferChecklistLabel(runData, id) {
  const summary = runData.summary || {};
  const verdict = runData.committee?.verdict || {};
  const tradeCards = Object.values(runData.tradeCards || {});
  const isSupplyDemand = runData.playbook?.key === "supply_demand_cycle";
  const tradeCard = tradeCards.find((card) => `${card.role}_${card.leg}` === id);
  if (tradeCard) {
    const parts = [];
    if (tradeCard.themeEntry) {
      parts.push(`主题入场 ${tradeCard.themeEntry}`);
    }
    if (tradeCard.confirmEntry) {
      parts.push(`确认 ${tradeCard.confirmEntry}`);
    }
    if (tradeCard.invalidation) {
      parts.push(`失效 ${tradeCard.invalidation}`);
    }
    return `${tradeCard.leg}: ${parts.join(" / ") || "等待条件"}`;
  }

  const labels = {
    event_status: "核验事件没有出现实质性缓和或协议突破",
    price_hike: "核验涨价/提价是否仍在兑现",
    supply_shortage: "核验供给是否继续紧张",
    high_utilization: "核验景气/稼动率是否仍维持高位",
    primary_leg: isSupplyDemand
      ? `核验 ${summary.primaryLeg || "主腿"} 仍是定价权最强主腿`
      : `核验 ${summary.primaryLeg || "主腿"} 仍是最稳主腿`,
    hedge_leg: `核验 ${summary.hedgeLeg || "对冲腿"} 仍承担第二层防守`,
    confirm_leg: isSupplyDemand
      ? `确认 ${summary.confirmLeg || "确认腿"} 只有在景气确认后才加仓`
      : `确认 ${summary.confirmLeg || "确认腿"} 只有在确认信号后才加仓`,
    quality: "核验企业质量是否仍然成立",
    capital_allocation: "核验资本配置与现金流质量",
    odds: "核验当前价格是否仍有赔率",
    holding_intent: "确认离开短期叙事后你是否仍愿继续持有",
    liquidity: "核验流动性方向是否仍在支持主线",
    cross_asset: "核验跨资产是否继续共振",
    macro_break: "确认关键宏观变量没有明显背离",
    default_structure: `默认结构：${verdict.defaultStructure || "待确认"}`,
    upgrade_path: `升级路径：${verdict.upgradePath || "待确认"}`,
    downgrade_sequence: `降级顺序：${verdict.downgradeSequence || "待确认"}`,
    do_not_do: `禁止动作：${verdict.doNotDo || "待确认"}`
  };
  return labels[id] || id;
}

function readJsonIfExists(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    if (error && (error.code === "ENOENT" || error.name === "SyntaxError")) {
      return {};
    }
    throw error;
  }
}

function findLatestLegendaryNote(wikiNotes, prefix) {
  const matches = wikiNotes.filter((note) => note.title.startsWith(prefix));
  if (matches.length === 0) {
    return null;
  }
  return [...matches].sort(compareLegendaryNotes)[0];
}

function compareLegendaryNotes(left, right) {
  const rightDate = String(right.frontmatter?.compiled_at || right.frontmatter?.kb_date || "");
  const leftDate = String(left.frontmatter?.compiled_at || left.frontmatter?.kb_date || "");
  if (rightDate !== leftDate) {
    return rightDate.localeCompare(leftDate);
  }
  return left.relativePath.localeCompare(right.relativePath);
}

function formatNoteRef(note) {
  if (!note) {
    return "(missing)";
  }
  return `${note.title} [${note.relativePath}]`;
}
