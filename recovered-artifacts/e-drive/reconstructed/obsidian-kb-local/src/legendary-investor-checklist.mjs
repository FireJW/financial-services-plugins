export function buildLegendaryInvestorChecklist(exportData, options = {}) {
  const payload = normalizeLegendaryExport(exportData);
  const generatedAt = options.generatedAt || new Date().toISOString();
  const baseChecklist = [
    ...buildPlaybookChecklistItems(payload),
    ...buildCommitteeChecklistItems(payload),
    ...buildTradeCardChecklistItems(payload)
  ];
  const checklist = applyChecklistState(baseChecklist, options.state);

  return {
    schemaVersion: 1,
    generatedAt,
    sourceSchemaVersion: payload.schemaVersion || null,
    playbook: payload.playbook,
    summary: payload.summary,
    committee: payload.committee,
    checklist
  };
}

export function renderLegendaryInvestorChecklist(report, options = {}) {
  const sourcePath = options.sourcePath || "";
  const statePath = options.statePath || "";
  const lines = [
    "Legendary Investor Checklist",
    "",
    sourcePath ? `Source: ${sourcePath}` : null,
    statePath ? `State: ${statePath}` : null,
    `Playbook: ${report.playbook.label}`,
    `Single Mentor: ${report.summary.singleMentor}`,
    `Committee Cap: ${report.committee.committeeMaxPosition}`,
    `Default Structure: ${report.committee.verdict.defaultStructure}`,
    `Upgrade Path: ${report.committee.verdict.upgradePath}`,
    `Downgrade Sequence: ${report.committee.verdict.downgradeSequence}`,
    ""
  ].filter(Boolean);

  for (const [category, label] of CATEGORY_LABELS) {
    const rows = report.checklist.filter((item) => item.category === category);
    if (rows.length === 0) {
      continue;
    }
    lines.push(`## ${label}`);
    for (const item of rows) {
      lines.push(`- [${item.checked ? "x" : " "}] ${item.label}`);
      if (item.originalLabel) {
        lines.push(`  en: ${item.originalLabel}`);
      }
      if (item.traderNote) {
        lines.push(`  trader: ${item.traderNote}`);
      }
      lines.push(`  why: ${item.rationale}`);
      if (item.note) {
        lines.push(`  note: ${item.note}`);
      }
      if (item.checkedAt) {
        lines.push(`  checked_at: ${item.checkedAt}`);
      }
    }
    lines.push("");
  }

  return lines.join("\n").trim();
}

function normalizeLegendaryExport(exportData) {
  const payload = exportData && typeof exportData === "object" ? exportData : {};
  return {
    schemaVersion: payload.schemaVersion || null,
    playbook: payload.playbook || {
      key: "event_driven_risk",
      label: "事件驱动风险委员会"
    },
    summary: payload.summary || {},
    committee: payload.committee || {
      committeeMaxPosition: "",
      verdict: {}
    },
    tradeCards: payload.tradeCards || {}
  };
}

function buildPlaybookChecklistItems(payload) {
  switch (payload.playbook.key) {
    case "valuation_quality":
      return [
        createItem(
          "preopen",
          "quality",
          "核验企业质量是否仍然成立",
          "Check business quality still holds",
          "先确认公司本身没有变味，别一边说长期主义，一边连质量有没有变都没重新看。",
          "先确认你买的是企业，而不是故事。"
        ),
        createItem(
          "preopen",
          "capital_allocation",
          "核验资本配置与现金流质量",
          "Check capital allocation and cash flow quality",
          "看看管理层花钱有没有继续靠谱，现金流是不是还真金白银，不要只盯着叙事。",
          "质量与估值委员会默认先看经营质量，再看价格。"
        ),
        createItem(
          "preopen",
          "odds",
          "核验当前价格是否仍有赔率",
          "Check current price still offers acceptable odds",
          "重点不是喜不喜欢公司，而是现在这个价位值不值得你承担未来失望的风险。",
          "如果价格继续扩张但质量证据没有同步变强，就该降级。"
        ),
        createItem(
          "preopen",
          "holding_intent",
          "确认离开短期叙事后你是否仍愿继续持有",
          "Confirm you would still hold without the short-term story",
          "问自己一句：如果明天没人再讲这个故事了，你还愿不愿意继续拿。",
          "这是区分投资和追价的关键。"
        )
      ];
    case "macro_reflexive":
      return [
        createItem(
          "preopen",
          "liquidity",
          "核验流动性方向是否仍在支持主线",
          "Check liquidity still supports the main expression",
          "先看钱往哪边走，而不是先相信自己宏观观点一定对。",
          "宏观反身性委员会先看流动性而不是单一叙事。"
        ),
        createItem(
          "preopen",
          "cross_asset",
          "核验跨资产是否继续共振",
          "Check cross-asset confirmation is still intact",
          "如果只有一个市场在动，别急着当成全市场共识。",
          "没有跨资产确认，就没有资格给方向性重仓。"
        ),
        createItem(
          "preopen",
          "macro_break",
          "确认关键宏观变量没有明显背离",
          "Confirm key macro variables are not diverging",
          "一旦链条开始打架，就先降加仓位，不要硬解释。",
          "链条一旦背离，先降加仓位。"
        )
      ];
    case "supply_demand_cycle":
      return [
        createItem(
          "preopen",
          "price_hike",
          "核验涨价/提价是否仍在兑现",
          "Check price hikes are still being confirmed",
          "先确认涨价不是停留在预期里，而是真的还在被市场和产业链验证。",
          "供需周期委员会先看涨价兑现，再看第二层弹性。"
        ),
        createItem(
          "preopen",
          "supply_shortage",
          "核验供给是否继续紧张",
          "Check supply remains tight",
          "确认供需偏紧没有开始松动，不然景气故事最先受伤。",
          "一旦供给修复快于预期，先想降级而不是补理由。"
        ),
        createItem(
          "preopen",
          "high_utilization",
          "核验景气/稼动率是否仍维持高位",
          "Check utilization and cycle strength remain elevated",
          "排产、稼动率、满产这些高景气信号要继续站在你这边。",
          "没有景气强化，弹性腿就不配升级。"
        ),
        createItem(
          "preopen",
          "primary_leg",
          `核验 ${payload.summary.primaryLeg} 仍是定价权最强主腿`,
          `Check ${payload.summary.primaryLeg} remains the cleanest pricing-power primary leg`,
          `先确认 ${payload.summary.primaryLeg} 仍是定价权和利润传导最硬的那条腿，不要被产业链热度带偏。`,
          "供需周期结构先看主腿的定价权，再看弹性。"
        ),
        createItem(
          "preopen",
          "confirm_leg",
          `确认 ${payload.summary.confirmLeg} 只有在景气确认后才加仓`,
          `Confirm ${payload.summary.confirmLeg} only gets sized up after cycle confirmation`,
          `${payload.summary.confirmLeg} 只能在涨价兑现、供需继续紧、景气确认后再放大，不是先抢跑。`,
          "加仓腿默认后置。"
        )
      ];
    default:
      return [
        createItem(
          "preopen",
          "event_status",
          "核验事件没有出现实质性缓和或协议突破",
          "Check no substantive de-escalation or agreement breakthrough",
          "先确认消息面没出现真正缓和或谈成；只要这条变了，今天这套结构就别硬上。",
          "事件驱动结构最怕把旧叙事当成新催化。"
        ),
        createItem(
          "preopen",
          "primary_leg",
          `核验 ${payload.summary.primaryLeg} 仍是最稳主腿`,
          `Check ${payload.summary.primaryLeg} is still the cleanest primary leg`,
          `先确认今天最该做的还是 ${payload.summary.primaryLeg}，别盘前还没想清楚就被弹性腿带跑。`,
          "委员会当前共识主腿必须先被确认。"
        ),
        createItem(
          "preopen",
          "hedge_leg",
          `核验 ${payload.summary.hedgeLeg} 仍承担第二层防守`,
          `Check ${payload.summary.hedgeLeg} still works as the hedge leg`,
          `确认 ${payload.summary.hedgeLeg} 还真能扛波动，不是摆着好看的装饰仓。`,
          "默认结构先主腿后防守腿，不是先追弹性。"
        ),
        createItem(
          "preopen",
          "confirm_leg",
          `确认 ${payload.summary.confirmLeg} 只有在确认信号后才加仓`,
          `Confirm ${payload.summary.confirmLeg} only gets sized up after confirmation`,
          `记住 ${payload.summary.confirmLeg} 只能后手加，不是盘前先抢跑的票。`,
          "加仓腿默认后置。"
        )
      ];
  }
}

function buildCommitteeChecklistItems(payload) {
  const verdict = payload.committee.verdict || {};
  return [
    createItem(
      "committee",
      "default_structure",
      `默认结构：${verdict.defaultStructure || "待确认"}`,
      "Default structure",
      "今天先按这个排兵布阵，不要一上来就把所有腿一起抬上去。",
      "先按委员会当前默认结构执行。"
    ),
    createItem(
      "committee",
      "upgrade_path",
      `升级路径：${verdict.upgradePath || "待确认"}`,
      "Upgrade path",
      "只有满足升级条件，才允许把后手腿抬成正式仓位。",
      "只有满足升级路径，才允许提高弹性或第三腿权重。"
    ),
    createItem(
      "committee",
      "downgrade_sequence",
      `降级顺序：${verdict.downgradeSequence || "待确认"}`,
      "Downgrade sequence",
      "一旦盘面或事实变坏，就按这个顺序撤，不要临场乱砍。",
      "一旦环境恶化或结构背离，按这个顺序撤退。"
    ),
    createItem(
      "committee",
      "do_not_do",
      `禁止动作：${verdict.doNotDo || "待确认"}`,
      "Do-not-do rules",
      "把这些当成今天绝对不能犯的错，别用盘中情绪去碰它。",
      "先知道什么不能做，才能避免把正确结构做坏。"
    )
  ];
}

function buildTradeCardChecklistItems(payload) {
  return Object.values(payload.tradeCards || {})
    .filter(Boolean)
    .map((card) => {
      const parts = [];
      if (card.themeEntry) {
        parts.push(`主题入场 ${card.themeEntry}`);
      }
      if (card.confirmEntry) {
        parts.push(`确认 ${card.confirmEntry}`);
      }
      if (card.invalidation) {
        parts.push(`失效 ${card.invalidation}`);
      }
      return createItem(
        "trade_cards",
        `${card.role}_${card.leg}`,
        `${card.leg}: ${parts.join(" / ") || "等待条件"}`,
        `${capitalizeRole(card.role)} trade card: ${card.leg}`,
        buildTradeCardTraderNote(card),
        `把 ${card.role} 角色的执行位写清楚，避免盘中漂移。`
      );
    });
}

function createItem(category, id, label, originalLabel, traderNote, rationale) {
  return {
    category,
    id,
    label,
    originalLabel,
    traderNote,
    rationale,
    checked: false,
    checkedAt: null,
    note: ""
  };
}

export function applyChecklistState(checklist, state) {
  const items = normalizeChecklistState(state).items;
  return checklist.map((item) => {
    const saved = items[item.id] || {};
    return {
      ...item,
      checked: saved.checked === true,
      checkedAt: saved.checkedAt || null,
      note: saved.note || ""
    };
  });
}

export function normalizeChecklistState(state) {
  const payload = state && typeof state === "object" ? state : {};
  return {
    schemaVersion: payload.schemaVersion || 1,
    updatedAt: payload.updatedAt || null,
    items: payload.items && typeof payload.items === "object" ? payload.items : {}
  };
}

export function updateChecklistState(currentState, command, options = {}) {
  const next = normalizeChecklistState(currentState);
  const updatedAt = options.updatedAt || new Date().toISOString();

  if (command.resetState) {
    next.items = {};
  }

  for (const id of command.checkIds || []) {
    next.items[id] = {
      ...(next.items[id] || {}),
      checked: true,
      checkedAt: updatedAt
    };
  }

  for (const id of command.uncheckIds || []) {
    next.items[id] = {
      ...(next.items[id] || {}),
      checked: false,
      checkedAt: null
    };
  }

  for (const [id, note] of Object.entries(command.notes || {})) {
    next.items[id] = {
      ...(next.items[id] || {}),
      note
    };
  }

  next.updatedAt = updatedAt;
  return next;
}

const CATEGORY_LABELS = new Map([
  ["preopen", "Pre-open Checks"],
  ["committee", "Committee Rules"],
  ["trade_cards", "Trade Cards"]
]);

function buildTradeCardTraderNote(card) {
  const parts = [];
  if (card.themeEntry) {
    parts.push(`${card.themeEntry} 先看主题位`);
  }
  if (card.confirmEntry) {
    parts.push(`${card.confirmEntry} 才算真确认`);
  }
  if (card.invalidation) {
    parts.push(`${card.invalidation} 就别硬扛`);
  }
  return `把 ${card.leg} 当成 ${capitalizeRole(card.role)} 来看，${parts.join("，")}。`;
}

function capitalizeRole(role) {
  const value = String(role || "").trim();
  if (!value) {
    return "Trade";
  }
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}
