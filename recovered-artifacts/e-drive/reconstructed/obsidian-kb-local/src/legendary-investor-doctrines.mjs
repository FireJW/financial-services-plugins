export const LEGENDARY_INVESTOR_DOCTRINES = {
  Druckenmiller: {
    name: "Druckenmiller",
    fitReason: "仓位、确认、风险切换和认错速度",
    voteBias: "momentum-confirmation",
    maxPositionGuidance: "{primaryLeg} 0.50 / {confirmLeg} 0.20 / {hedgeLeg} 0.30",
    evidenceFocus: "主腿催化映射最直接，弹性腿必须等确认，headline 不能替代 tape。",
    killSwitchFocus: "油运高开过多、缓和 headline、或 {confirmLeg} 未过确认位时，不准提高弹性腿权重。",
    criticOpeners: [
      "Druckenmiller 会先问：如果真正的催化还没有被 tape 证明，为什么要把 {confirmLeg} 提前放进主执行序列？",
      "他真正关心的不是你有没有故事，而是你有没有在正确的时点、用正确的仓位，去做最干净的那条腿。"
    ],
    singleMentorLead:
      "Druckenmiller 会这么说：做最干净的那条腿。先做 {primaryLeg}，让 {confirmLeg} 只在确认后上桌，让 {hedgeLeg} 用来防 headline 抽脸。",
    singleMentorBelief:
      "核心认知：你不是在押最终世界观，你是在押“催化仍被 tape 支持”的那一小段。",
    roundtableStance:
      "Druckenmiller：主腿应该是 {primaryLeg}，因为它的催化映射最直接；{confirmLeg} 必须让位给确认。",
    reviewPrompt:
      "Druckenmiller 式复盘会盯住：你有没有在 {confirmEntry} 出现前就先给了 {confirmLeg} 过高仓位。",
    playbookOverrides: {
      supply_demand_cycle: {
        criticOpeners: [
          "Druckenmiller 会先问：如果涨价和景气还没有被 tape 证明，为什么要把 {confirmLeg} 提前放进主执行序列？"
        ],
        roundtableStance:
          "Druckenmiller：先做涨价兑现映射最直接的 {primaryLeg}，{confirmLeg} 只能在景气确认后参与。",
        evidenceFocus:
          "主腿涨价兑现映射最直接，弹性腿必须等确认，景气预期不能替代 tape。",
        killSwitchFocus:
          "如果涨价落地弱于预期、供给修复、或 {confirmLeg} 未过确认位，不准提高弹性腿权重。"
      },
      macro_reflexive: {
        criticOpeners: [
          "Druckenmiller 会先问：如果传导链还没有被价格和跨资产验证，为什么要把 {confirmLeg} 提前放进主执行序列？"
        ],
        roundtableStance:
          "Druckenmiller：先做价格与催化映射最直接的 {primaryLeg}，{confirmLeg} 只能在传导链确认后参与。"
      }
    }
  },
  "Howard Marks": {
    name: "Howard Marks",
    fitReason: "中间态判断、风险预算和错配识别",
    voteBias: "middle-state-risk-budget",
    maxPositionGuidance: "{primaryLeg} 0.45 / {hedgeLeg} 0.35 / {confirmLeg} 0.15",
    evidenceFocus: "当前只是风险未解除，不是继续升级确认，第二层表达应优先保护本金与容错。",
    killSwitchFocus: "如果市场已提前交易溢价，或新闻没有新增强化，就下调弹性腿并优先保留对冲。",
    criticOpeners: [
      "Howard Marks 会补一句：你现在拥有的是“风险未解除”，不是“风险会继续扩张”的高置信度证据，所以仓位强度必须低于叙事强度。",
      "他还会继续追问：如果市场已经提前交易过一部分风险溢价，那你现在拿什么证明自己不是在接最后一棒？"
    ],
    singleMentorLead:
      "Howard Marks 会这么说：先判断你知道什么、不知道什么。{primaryLeg} 可以是主线，但 {confirmLeg} 只能在赔率改善后参与。",
    singleMentorBelief:
      "核心认知：当前是中间态，最重要的不是赚到每一段，而是别在证据模糊时把自己暴露得过深。",
    roundtableStance:
      "Howard Marks：当前是中间态，不是重仓猛攻态。第二笔更该优先考虑 {hedgeLeg}，因为它更能处理消息反转。",
    reviewPrompt:
      "Howard Marks 式复盘先问：你赚的是事实的钱，还是情绪和运气的钱？",
    actionCardNote:
      "哲学备注：这不是“彻底升级确认”环境，所以仓位逻辑必须更接近 Howard Marks 的风险预算，而不是单边满仓进攻。",
    playbookOverrides: {
      supply_demand_cycle: {
        criticOpeners: [
          "Howard Marks 会补一句：你现在拥有的是供需偏紧，不是业绩已经完整兑现，所以仓位强度必须低于景气叙事强度。"
        ],
        roundtableStance:
          "Howard Marks：当前是中间态，不是景气满仓猛攻态。第二笔更该优先考虑 {hedgeLeg}，因为它更能处理涨价不及预期或供给修复。",
        evidenceFocus:
          "当前只是供需偏紧，不是业绩完全兑现，第二层表达应优先保护本金与容错。",
        killSwitchFocus:
          "如果涨价没有新增兑现、供给修复、或市场已提前交易过大部分景气，就下调弹性腿并优先保留防守。"
      },
      valuation_quality: {
        criticOpeners: [
          "Howard Marks 会补一句：高质量不等于任何价格都安全，风险首先来自你付出的价格，而不只是企业本身。",
          "他还会追问：如果这家公司确实优秀，市场为什么还会把便宜价格留给你？你面对的是错杀，还是自己在美化高估值？"
        ],
        singleMentorLead:
          "Howard Marks 会这么说：先判断质量是不是你真的理解的质量，再判断这个价格是不是值得你承担未来的失望风险。",
        singleMentorBelief:
          "核心认知：好资产也可能是坏交易，关键不是你喜不喜欢企业，而是现在的赔率是否仍值得你出手。",
        roundtableStance:
          "Howard Marks：当前更该优先考虑价格与风险预算，而不是先假设优秀公司自然会覆盖掉过高买入价。",
        reviewPrompt:
          "Howard Marks 式复盘先问：你赚的是企业价值兑现的钱，还是市场愿意继续抬高估值的钱？",
        evidenceFocus:
          "质量判断必须和价格纪律绑定，否则所谓长期主义只是在替当前高价背书。",
        killSwitchFocus:
          "如果价格继续扩张但质量证据没有同步变强，就该降级仓位而不是继续加码。"
      },
      macro_reflexive: {
        criticOpeners: [
          "Howard Marks 会补一句：宏观判断最容易高估确定性，仓位强度必须低于你对传导链的确信度。"
        ],
        roundtableStance:
          "Howard Marks：先看风险预算，再看宏观方向；如果链条只证实了一半，就不要先用满仓去补完另一半。"
      }
    }
  },
  Dalio: {
    name: "Dalio",
    fitReason: "流动性、风险溢价和跨资产链条",
    voteBias: "cross-asset-confirmation",
    maxPositionGuidance: "{primaryLeg} 0.40 / {hedgeLeg} 0.25 / {confirmLeg} 0.15",
    evidenceFocus: "这不是单票问题，而是 Brent、油运风险溢价、黄金避险三者是否共振的问题。",
    killSwitchFocus: "如果 Brent 不强、黄金不同步、或三条腿开始分化，就不能维持进攻型三腿结构。",
    criticOpeners: [
      "Dalio 会追问：如果这是风险溢价、流动性和避险共振的交易，那三条腿之间是否真的互相确认，还是你只是在同一事件上重复下注？"
    ],
    singleMentorLead:
      "Dalio 会这么说：先把事件放进流动性、风险偏好和跨资产确认链里，再决定每一条腿是否应该存在。",
    singleMentorBelief:
      "核心认知：这不是单票判断，而是一个“原油 / 油运 / 黄金”之间是否共振的问题。",
    roundtableStance:
      "Dalio：这是风险溢价、流动性和避险共振的交易，不是企业慢变量交易，所以三条腿都要服从 headline 和跨资产确认。",
    playbookOverrides: {
      macro_reflexive: {
        criticOpeners: [
          "Dalio 会追问：你说的是宏观观点，还是已经被跨资产和流动性共同验证的宏观结构？"
        ],
        singleMentorLead:
          "Dalio 会这么说：先看流动性、利率、美元和风险偏好是否共同指向同一个方向，再决定每一层结构是否应该存在。",
        singleMentorBelief:
          "核心认知：单一宏观观点不值钱，能不能赚钱取决于它有没有形成跨资产共振和可执行结构。",
        roundtableStance:
          "Dalio：这不是单票选择题，而是流动性、利率、美元和风险资产是否正在共同讲同一个故事。"
      }
    }
  },
  Buffett: {
    name: "Buffett",
    fitReason: "企业质量、资本配置和持有纪律",
    voteBias: "quality-first",
    maxPositionGuidance: "{primaryLeg} 0.35 / {hedgeLeg} 0.10 / {confirmLeg} 0.05",
    evidenceFocus: "如果离开 headline 这条腿就不值得拿，那么不能用长期语言为短线仓位背书。",
    killSwitchFocus: "一旦 thesis 只剩 headline，没有企业质量与持有逻辑支撑，就不该扩大仓位。",
    criticOpeners: [
      "Buffett 会反问：如果离开这次 headline，你还愿意持有 {primaryLeg} 吗？如果不愿意，那这其实不是投资，而只是事件票。"
    ],
    singleMentorLead:
      "Buffett 会这么说：如果这只是事件表达，不要把它伪装成长长期确定性；先分清什么是交易，什么才配被长期持有。",
    singleMentorBelief:
      "核心认知：不要因为短期事件而给自己虚假的长期确信度。",
    roundtableStance:
      "Buffett：如果组合里的逻辑主要来自 headline，而不是企业自身，就不能拿长期投资的语言美化短线仓位。",
    playbookOverrides: {
      supply_demand_cycle: {
        criticOpeners: [
          "Buffett 会反问：如果没有定价权和成本转嫁能力，这轮涨价到底会落到谁的利润表，而你为什么默认是 {primaryLeg}？"
        ],
        singleMentorLead:
          "Buffett 会这么说：先分清这是不是一次性景气波动，还是企业真的拥有把涨价传导成利润的定价权。",
        singleMentorBelief:
          "核心认知：供需偏紧不等于每家公司都有定价权，只有真正能把涨价落到利润的公司才配做主腿。",
        roundtableStance:
          "Buffett：只有真正具备定价权和成本转嫁能力的公司，才配成为 {primaryLeg}；其余标的最多是景气弹性仓。",
        reviewPrompt:
          "Buffett 式复盘先问：你有没有把行业景气错当成企业护城河，或者把一次性涨价错当成长期定价权？",
        evidenceFocus:
          "要看定价权、成本转嫁和企业质量，而不是只看产业景气或涨价故事。",
        killSwitchFocus:
          "如果涨价传导不到利润，或者企业没有你以为的定价权，就不该扩大仓位。"
      },
      valuation_quality: {
        criticOpeners: [
          "Buffett 会反问：如果价格再便宜一些你会更兴奋，那为什么现在要急着把一家好公司买成一笔差交易？"
        ],
        singleMentorLead:
          "Buffett 会这么说：先分清你是看中了企业，还是只是想尽快拥有一个你喜欢的故事；真正的纪律是在好公司面前也愿意等价格。",
        singleMentorBelief:
          "核心认知：优秀公司值得长期持有，但并不值得在任何价格被买入。",
        roundtableStance:
          "Buffett：如果企业质量真好，那你要保护的不是出手机会，而是未来很多年的回报起点。",
        reviewPrompt:
          "Buffett 式复盘先问：如果市场明天停盘五年，你还会因为今天这个价格而安心持有吗？",
        evidenceFocus:
          "企业质量、资本配置和长期持有意愿必须同时成立，否则所谓价值投资只是对好故事的追价。",
        killSwitchFocus:
          "如果你发现离开短期叙事就不愿继续持有，或者价格已经透支多年回报，就不该扩大仓位。"
      }
    }
  },
  GMO: {
    name: "GMO",
    fitReason: "估值纪律、均值回归和泡沫警惕",
    voteBias: "price-discipline",
    maxPositionGuidance: "{primaryLeg} 0.30 / {hedgeLeg} 0.15 / {confirmLeg} 0.10",
    evidenceFocus: "事件可以给催化，但不能消灭坏赔率，尤其不能替代追高纪律。",
    killSwitchFocus: "当价格已远离确认位或市场提前交易过大部分溢价时，宁可错过也不要追。",
    criticOpeners: [
      "GMO 会提醒：最危险的不是事件本身，而是你因为事件而愿意接受多差的赔率与多差的追价。"
    ],
    singleMentorLead:
      "GMO 会这么说：事件可以给催化，但不会替你抹掉坏赔率；最应该防的是在情绪最高处付出最差价格。",
    singleMentorBelief:
      "核心认知：事件不能替代估值与赔率纪律，尤其不能替代你对追高风险的克制。",
    roundtableStance:
      "GMO：如果市场已经提前交易了相当一部分风险溢价，就别把“逻辑没死”当成“赔率还在”。",
    playbookOverrides: {
      valuation_quality: {
        criticOpeners: [
          "GMO 会提醒：最危险的不是错过好公司，而是用一个多年回报会被稀释的价格去证明自己理解了好公司。"
        ],
        singleMentorLead:
          "GMO 会这么说：质量和赔率从来不是二选一；越好的公司，越需要你避免在最贵的时候付出最差回报起点。",
        singleMentorBelief:
          "核心认知：好资产也必须服从赔率和均值回归，越是高质量，越不能让自己失去价格纪律。",
        roundtableStance:
          "GMO：如果今天的价格已经提前透支了很多年的优秀，你就不能把“公司很好”自动翻译成“现在值得买”。",
        reviewPrompt:
          "GMO 式复盘会盯住：你到底是在买质量，还是在为别人已经抬高的预期接盘？",
        evidenceFocus:
          "质量判断不能替代赔率，真正的关键是当前价格是否仍允许你在未来获得足够回报。",
        killSwitchFocus:
          "如果价格继续扩张、赔率继续恶化，哪怕公司依旧优秀，也该先退后而不是硬上。"
      }
    }
  },
  "Hard Lessons": {
    name: "Hard Lessons",
    fitReason: "执行错误、纠偏动作与复盘纪律",
    reviewPrompt:
      "Hard Lessons 式复盘再问：你最像在哪一刻把“等待确认”改成了“先上车再说”？"
  }
};

export const LEGENDARY_ROUNDTABLE_PLAYBOOKS = {
  event_driven_risk: {
    key: "event_driven_risk",
    label: "事件驱动风险委员会",
    mentors: ["Druckenmiller", "Howard Marks", "Dalio"],
    rationale: "适合 headline、风险溢价、确认位、对冲腿和跨资产共振驱动的案例。"
  },
  valuation_quality: {
    key: "valuation_quality",
    label: "估值与质量委员会",
    mentors: ["Buffett", "Howard Marks", "GMO"],
    rationale: "适合护城河、资本配置、长期持有、估值纪律与赔率约束驱动的案例。"
  },
  macro_reflexive: {
    key: "macro_reflexive",
    label: "宏观反身性委员会",
    mentors: ["Dalio", "Druckenmiller", "GMO"],
    rationale: "适合流动性、跨资产、风险偏好、赔率压缩和宏观传导链驱动的案例。"
  },
  supply_demand_cycle: {
    key: "supply_demand_cycle",
    label: "供需周期委员会",
    mentors: ["Druckenmiller", "Howard Marks", "Buffett"],
    rationale:
      "适合涨价周期、供需紧缺、产业链瓶颈驱动的案例。Buffett 关注定价权和企业质量，Druckenmiller 关注仓位和确认，Howard Marks 关注风险预算。",
    defaultContext: {
      primaryLeg: "涨价兑现最直接标的",
      confirmLeg: "景气确认后参与标的",
      hedgeLeg: "防守/对冲标的",
      confirmEntry: "景气数据确认信号"
    },
    scenarioTemplates: [
      {
        label: "price_hike_confirmation",
        trigger: "涨价落地+订单确认",
        primaryWeight: 0.50,
        confirmWeight: 0.20,
        hedgeWeight: 0.30
      },
      {
        label: "supply_tightness_early",
        trigger: "供需偏紧但未完全兑现",
        primaryWeight: 0.40,
        confirmWeight: 0.15,
        hedgeWeight: 0.35
      }
    ]
  }
};

export function getLegendaryDoctrine(name) {
  return LEGENDARY_INVESTOR_DOCTRINES[name] || null;
}

export function getLegendaryRoundtablePlaybook(key) {
  return LEGENDARY_ROUNDTABLE_PLAYBOOKS[key] || LEGENDARY_ROUNDTABLE_PLAYBOOKS.event_driven_risk;
}

export function renderDoctrineLine(name, field, params = {}, fallback = "") {
  const doctrine = getLegendaryDoctrine(name);
  const template = doctrine?.[field];
  if (typeof template !== "string") {
    return fallback;
  }
  return fillDoctrineTemplate(template, params);
}

export function renderDoctrineLines(name, field, params = {}) {
  const doctrine = getLegendaryDoctrine(name);
  const templates = doctrine?.[field];
  if (!Array.isArray(templates)) {
    return [];
  }
  return templates.map((template) => fillDoctrineTemplate(template, params));
}

export function renderDoctrineLineForPlaybook(name, field, playbookKey, params = {}, fallback = "") {
  const template = resolveDoctrineTemplate(name, field, playbookKey);
  if (typeof template !== "string") {
    return fallback;
  }
  return fillDoctrineTemplate(template, params);
}

export function renderDoctrineLinesForPlaybook(name, field, playbookKey, params = {}) {
  const templates = resolveDoctrineTemplate(name, field, playbookKey);
  if (!Array.isArray(templates)) {
    return [];
  }
  return templates.map((template) => fillDoctrineTemplate(template, params));
}

function resolveDoctrineTemplate(name, field, playbookKey) {
  const doctrine = getLegendaryDoctrine(name);
  const override = doctrine?.playbookOverrides?.[playbookKey]?.[field];
  if (override !== undefined) {
    return override;
  }
  return doctrine?.[field];
}

function fillDoctrineTemplate(template, params) {
  return String(template || "").replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, key) =>
    Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : ""
  );
}

// ── Delta Interpretation Frameworks ──────────────────────────────────────

/**
 * Each mentor interprets the same delta through a different reasoning framework.
 * This is not a style/tone change — it's a structural difference in what each
 * mentor considers important, what they'd act on, and what they'd ignore.
 */

const DELTA_INTERPRETATION_FRAMEWORKS = {
  Druckenmiller: {
    name: "Druckenmiller",
    focusAreas: ["momentum", "tape_confirmation", "position_sizing", "speed_of_recognition"],
    interpretNewFact(factKey, factValue) {
      // Druckenmiller cares about: is this a momentum signal? Does it confirm tape?
      if (/brent|oil|price/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Brent/price change is a direct tape signal. If direction aligns with thesis, size up. If not, cut fast.`,
          action: "size_adjustment"
        };
      }
      if (/agreement|negotiation|headline/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Headline change is a catalyst signal. React to tape, not to narrative. If tape doesn't confirm, the headline doesn't matter.`,
          action: "catalyst_reassessment"
        };
      }
      if (/gold|hedge|safe.?haven/i.test(factKey)) {
        return {
          relevance: "medium",
          interpretation: `Gold/hedge move is a cross-asset confirmation signal. Only matters if it confirms or denies the primary leg's momentum.`,
          action: "cross_check"
        };
      }
      return {
        relevance: "low",
        interpretation: `Not a momentum-relevant signal. Monitor but don't act.`,
        action: "monitor"
      };
    },
    interpretConclusionChange(key, status) {
      if (status === "invalidated") {
        return `Druckenmiller: Invalidated conclusion "${key}" means cut immediately. Don't wait for confirmation of the invalidation — the first loss is the best loss.`;
      }
      if (status === "upgraded") {
        return `Druckenmiller: Upgraded conclusion "${key}" means the tape is confirming. Consider sizing up the primary leg if the risk/reward improved.`;
      }
      return null;
    },
    buildDeltaVerdict(delta) {
      if (delta.isFirstRun) return null;
      const signals = [];
      if (delta.changedFacts.length > 0) {
        signals.push(`${delta.changedFacts.length} fact(s) changed — check if tape confirms the new direction.`);
      }
      if (delta.conclusionsInvalidated.length > 0) {
        signals.push(`${delta.conclusionsInvalidated.length} conclusion(s) invalidated — cut exposure on affected legs immediately.`);
      }
      if (delta.conclusionsUpgraded.length > 0) {
        signals.push(`${delta.conclusionsUpgraded.length} conclusion(s) upgraded — consider sizing up if tape aligns.`);
      }
      if (signals.length === 0) return null;
      return {
        mentor: "Druckenmiller",
        framework: "momentum-confirmation",
        verdict: signals.join(" "),
        actionBias: delta.conclusionsInvalidated.length > 0 ? "reduce" : "hold_or_increase"
      };
    }
  },

  "Howard Marks": {
    name: "Howard Marks",
    focusAreas: ["risk_budget", "middle_state", "mismatch_detection", "second_level_thinking"],
    interpretNewFact(factKey, factValue) {
      if (/brent|oil|price/i.test(factKey)) {
        return {
          relevance: "medium",
          interpretation: `Price change alone doesn't tell you if risk/reward improved. Ask: has the market already priced this in? Are you buying at a better or worse risk budget?`,
          action: "risk_budget_check"
        };
      }
      if (/agreement|negotiation|headline/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Headline change shifts the middle-state probability. Key question: does this move you from "risk not released" to "risk releasing" or just noise?`,
          action: "probability_reassessment"
        };
      }
      if (/gold|hedge|safe.?haven/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Hedge asset movement tells you about market's risk appetite. If gold diverges from your thesis, your risk budget may be wrong.`,
          action: "hedge_effectiveness_check"
        };
      }
      return {
        relevance: "medium",
        interpretation: `New information. Ask: does this change what I know vs. what I don't know? Does it change my risk budget?`,
        action: "reassess"
      };
    },
    interpretConclusionChange(key, status) {
      if (status === "invalidated") {
        return `Howard Marks: Invalidated conclusion "${key}" means your risk budget was based on wrong assumptions. Reduce to a level where being wrong is survivable.`;
      }
      if (status === "upgraded") {
        return `Howard Marks: Upgraded conclusion "${key}" — but ask yourself: are you upgrading because of evidence, or because the price moved in your favor?`;
      }
      return null;
    },
    buildDeltaVerdict(delta) {
      if (delta.isFirstRun) return null;
      const signals = [];
      if (delta.changedFacts.length > 0) {
        signals.push(`${delta.changedFacts.length} fact(s) changed — reassess whether your risk budget still matches the new information landscape.`);
      }
      if (delta.conclusionsInvalidated.length > 0) {
        signals.push(`${delta.conclusionsInvalidated.length} conclusion(s) invalidated — this is a risk budget event, not just a thesis event. Reduce exposure to survivable levels.`);
      }
      if (delta.conclusionsUpgraded.length > 0) {
        signals.push(`${delta.conclusionsUpgraded.length} conclusion(s) upgraded — verify this is evidence-driven, not price-driven confirmation bias.`);
      }
      if (signals.length === 0) return null;
      return {
        mentor: "Howard Marks",
        framework: "risk-budget-middle-state",
        verdict: signals.join(" "),
        actionBias: delta.conclusionsInvalidated.length > 0 ? "reduce_to_survivable" : "maintain_discipline"
      };
    }
  },

  Dalio: {
    name: "Dalio",
    focusAreas: ["cross_asset_confirmation", "liquidity", "reflexivity", "macro_chain"],
    interpretNewFact(factKey, factValue) {
      if (/brent|oil|price/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Oil price change is one link in the macro chain. Check: is USD moving consistently? Is risk appetite shifting? Is the whole chain confirming or just one asset?`,
          action: "chain_verification"
        };
      }
      if (/agreement|negotiation|headline/i.test(factKey)) {
        return {
          relevance: "medium",
          interpretation: `Geopolitical headline changes the reflexivity loop. If markets already positioned for this, the reflexive effect may be exhausted.`,
          action: "reflexivity_check"
        };
      }
      if (/gold|hedge|safe.?haven/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Gold/safe-haven movement is a direct cross-asset signal. If gold and oil diverge, the macro chain is breaking — reduce all legs.`,
          action: "cross_asset_divergence_check"
        };
      }
      return {
        relevance: "low",
        interpretation: `Single-asset signal without cross-asset confirmation. Wait for the chain to speak.`,
        action: "wait_for_chain"
      };
    },
    interpretConclusionChange(key, status) {
      if (status === "invalidated") {
        return `Dalio: Invalidated conclusion "${key}" means the cross-asset chain broke. Don't just cut one leg — reassess the entire structure.`;
      }
      if (status === "upgraded") {
        return `Dalio: Upgraded conclusion "${key}" — only meaningful if multiple assets are confirming simultaneously. Single-asset upgrades are noise.`;
      }
      return null;
    },
    buildDeltaVerdict(delta) {
      if (delta.isFirstRun) return null;
      const signals = [];
      if (delta.changedFacts.length > 0) {
        signals.push(`${delta.changedFacts.length} fact(s) changed — verify cross-asset chain coherence before acting.`);
      }
      if (delta.conclusionsInvalidated.length > 0) {
        signals.push(`${delta.conclusionsInvalidated.length} conclusion(s) invalidated — treat as chain break. Reassess entire structure, not just the affected leg.`);
      }
      if (signals.length === 0) return null;
      return {
        mentor: "Dalio",
        framework: "cross-asset-chain",
        verdict: signals.join(" "),
        actionBias: delta.conclusionsInvalidated.length > 0 ? "reassess_structure" : "verify_chain"
      };
    }
  },

  Buffett: {
    name: "Buffett",
    focusAreas: ["business_quality", "pricing_power", "long_term_holding", "margin_of_safety"],
    interpretNewFact(factKey, factValue) {
      if (/brent|oil|price/i.test(factKey)) {
        return {
          relevance: "low",
          interpretation: `Short-term price movement is noise. The only question: does this company still have the same business quality and pricing power tomorrow?`,
          action: "ignore_unless_fundamental"
        };
      }
      if (/agreement|negotiation|headline/i.test(factKey)) {
        return {
          relevance: "low",
          interpretation: `Headlines come and go. If you wouldn't hold this stock without the headline, you shouldn't hold it with the headline.`,
          action: "headline_independence_test"
        };
      }
      if (/quality|moat|pricing.?power|capital.?allocation/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Business quality change is the only signal that matters. If the moat is widening, hold. If narrowing, reassess everything.`,
          action: "fundamental_reassessment"
        };
      }
      return {
        relevance: "low",
        interpretation: `Not a business-quality signal. Ignore for position decisions.`,
        action: "ignore"
      };
    },
    interpretConclusionChange(key, status) {
      if (status === "invalidated") {
        return `Buffett: Invalidated conclusion "${key}" — if this was about business quality, sell. If it was about price or headline, it probably doesn't matter.`;
      }
      if (status === "upgraded") {
        return `Buffett: Upgraded conclusion "${key}" — only act on it if the upgrade is about the business, not about the stock price.`;
      }
      return null;
    },
    buildDeltaVerdict(delta) {
      if (delta.isFirstRun) return null;
      const signals = [];
      if (delta.conclusionsInvalidated.length > 0) {
        signals.push(`${delta.conclusionsInvalidated.length} conclusion(s) invalidated — check if any relate to business quality. If yes, exit. If only price/headline, ignore.`);
      }
      if (delta.changedFacts.length > 0) {
        signals.push(`${delta.changedFacts.length} fact(s) changed — filter for business-quality signals only. Price and headline changes are noise.`);
      }
      if (signals.length === 0) return null;
      return {
        mentor: "Buffett",
        framework: "business-quality-filter",
        verdict: signals.join(" "),
        actionBias: "hold_unless_quality_impaired"
      };
    }
  },

  GMO: {
    name: "GMO",
    focusAreas: ["valuation_discipline", "mean_reversion", "bubble_detection", "price_discipline"],
    interpretNewFact(factKey, factValue) {
      if (/brent|oil|price/i.test(factKey)) {
        return {
          relevance: "high",
          interpretation: `Price change directly affects risk/reward ratio. If price moved further from fair value, the trade got worse, not better — regardless of narrative.`,
          action: "valuation_reassessment"
        };
      }
      if (/agreement|negotiation|headline/i.test(factKey)) {
        return {
          relevance: "medium",
          interpretation: `Headlines can create temporary mispricings. The question is: did the headline move price closer to or further from fair value?`,
          action: "mispricing_check"
        };
      }
      return {
        relevance: "medium",
        interpretation: `Assess impact on valuation and mean-reversion trajectory. Events don't change fair value — they change the path to get there.`,
        action: "valuation_path_check"
      };
    },
    interpretConclusionChange(key, status) {
      if (status === "invalidated") {
        return `GMO: Invalidated conclusion "${key}" — if the valuation thesis broke, exit. Don't let narrative rescue a bad price.`;
      }
      if (status === "upgraded") {
        return `GMO: Upgraded conclusion "${key}" — only meaningful if it improved the risk/reward ratio. If price also went up, the upgrade may be priced in.`;
      }
      return null;
    },
    buildDeltaVerdict(delta) {
      if (delta.isFirstRun) return null;
      const signals = [];
      if (delta.changedFacts.length > 0) {
        signals.push(`${delta.changedFacts.length} fact(s) changed — reassess valuation and risk/reward. If price moved away from fair value, reduce.`);
      }
      if (delta.conclusionsInvalidated.length > 0) {
        signals.push(`${delta.conclusionsInvalidated.length} conclusion(s) invalidated — don't let narrative rescue a broken valuation thesis.`);
      }
      if (signals.length === 0) return null;
      return {
        mentor: "GMO",
        framework: "valuation-discipline",
        verdict: signals.join(" "),
        actionBias: "reduce_if_overvalued"
      };
    }
  }
};

/**
 * Get the delta interpretation framework for a specific mentor.
 */
export function getDeltaInterpretationFramework(mentorName) {
  return DELTA_INTERPRETATION_FRAMEWORKS[mentorName] || null;
}

/**
 * Run all mentors' delta interpretation on the same delta, producing
 * a structured multi-perspective analysis.
 */
export function buildMultiMentorDeltaAnalysis(delta, mentorNames = []) {
  if (!delta || delta.isFirstRun) {
    return null;
  }

  const mentors = mentorNames.length > 0
    ? mentorNames
    : Object.keys(DELTA_INTERPRETATION_FRAMEWORKS);

  const analysis = {
    mentorVerdicts: [],
    factInterpretations: {},
    conclusionInterpretations: [],
    consensusAction: null,
    disagreements: []
  };

  // Collect verdicts
  for (const name of mentors) {
    const framework = DELTA_INTERPRETATION_FRAMEWORKS[name];
    if (!framework) continue;
    const verdict = framework.buildDeltaVerdict(delta);
    if (verdict) {
      analysis.mentorVerdicts.push(verdict);
    }
  }

  // Collect per-fact interpretations
  for (const factKey of [...delta.newFacts, ...delta.changedFacts]) {
    analysis.factInterpretations[factKey] = [];
    for (const name of mentors) {
      const framework = DELTA_INTERPRETATION_FRAMEWORKS[name];
      if (!framework) continue;
      const interpretation = framework.interpretNewFact(factKey, null);
      analysis.factInterpretations[factKey].push({
        mentor: name,
        ...interpretation
      });
    }
  }

  // Collect conclusion change interpretations
  for (const key of delta.conclusionsUpgraded) {
    for (const name of mentors) {
      const framework = DELTA_INTERPRETATION_FRAMEWORKS[name];
      if (!framework) continue;
      const interpretation = framework.interpretConclusionChange(key, "upgraded");
      if (interpretation) {
        analysis.conclusionInterpretations.push({ mentor: name, key, status: "upgraded", interpretation });
      }
    }
  }
  for (const key of delta.conclusionsInvalidated) {
    for (const name of mentors) {
      const framework = DELTA_INTERPRETATION_FRAMEWORKS[name];
      if (!framework) continue;
      const interpretation = framework.interpretConclusionChange(key, "invalidated");
      if (interpretation) {
        analysis.conclusionInterpretations.push({ mentor: name, key, status: "invalidated", interpretation });
      }
    }
  }

  // Derive consensus and disagreements
  const actionBiases = analysis.mentorVerdicts.map((v) => v.actionBias).filter(Boolean);
  const uniqueBiases = [...new Set(actionBiases)];
  if (uniqueBiases.length === 1) {
    analysis.consensusAction = uniqueBiases[0];
  } else if (uniqueBiases.length > 1) {
    // Find disagreements: mentors who want to reduce vs hold/increase
    const reducers = analysis.mentorVerdicts.filter((v) =>
      /reduce|cut|reassess/.test(v.actionBias || "")
    );
    const holders = analysis.mentorVerdicts.filter((v) =>
      /hold|increase|maintain|verify/.test(v.actionBias || "")
    );
    if (reducers.length > 0 && holders.length > 0) {
      analysis.disagreements.push({
        issue: "Position direction",
        reducers: reducers.map((v) => v.mentor),
        holders: holders.map((v) => v.mentor),
        resolution: reducers.length >= holders.length
          ? "Majority favors reducing. Default to the more conservative position."
          : "Majority favors holding. But if any reducer cites invalidation, respect the cut."
      });
    }
    analysis.consensusAction = reducers.length >= holders.length ? "reduce" : "hold";
  }

  return analysis;
}

/**
 * Format multi-mentor delta analysis as a markdown block.
 */
export function formatMultiMentorDeltaBlock(analysis) {
  if (!analysis) {
    return "";
  }

  const lines = ["## Multi-Mentor Delta Analysis", ""];

  // Verdicts
  if (analysis.mentorVerdicts.length > 0) {
    lines.push("### Mentor Verdicts");
    lines.push("");
    lines.push("| Mentor | Framework | Action Bias | Verdict |");
    lines.push("|--------|-----------|-------------|---------|");
    for (const v of analysis.mentorVerdicts) {
      const shortVerdict = v.verdict.length > 80 ? `${v.verdict.slice(0, 77)}...` : v.verdict;
      lines.push(`| ${v.mentor} | ${v.framework} | ${v.actionBias} | ${shortVerdict} |`);
    }
    lines.push("");
  }

  // Fact interpretations (only show where mentors disagree on relevance)
  const factKeys = Object.keys(analysis.factInterpretations);
  if (factKeys.length > 0) {
    lines.push("### Fact Interpretations");
    lines.push("");
    for (const factKey of factKeys.slice(0, 5)) {
      const interpretations = analysis.factInterpretations[factKey];
      const relevances = interpretations.map((i) => i.relevance);
      const hasDisagreement = new Set(relevances).size > 1;
      if (hasDisagreement) {
        lines.push(`**${factKey}** (mentors disagree on relevance):`);
        for (const i of interpretations) {
          lines.push(`- ${i.mentor} [${i.relevance}]: ${i.interpretation}`);
        }
        lines.push("");
      }
    }
  }

  // Conclusion interpretations
  if (analysis.conclusionInterpretations.length > 0) {
    lines.push("### Conclusion Change Interpretations");
    lines.push("");
    for (const ci of analysis.conclusionInterpretations) {
      lines.push(`- ${ci.interpretation}`);
    }
    lines.push("");
  }

  // Disagreements
  if (analysis.disagreements.length > 0) {
    lines.push("### Disagreements That Affect Execution");
    lines.push("");
    for (const d of analysis.disagreements) {
      lines.push(`- **${d.issue}**: ${d.reducers.join(", ")} want to reduce; ${d.holders.join(", ")} want to hold.`);
      lines.push(`  Resolution: ${d.resolution}`);
    }
    lines.push("");
  }

  // Consensus
  if (analysis.consensusAction) {
    lines.push(`### Consensus Action: **${analysis.consensusAction}**`);
  }

  return lines.join("\n");
}
