import {
  getLegendaryDoctrine,
  getLegendaryRoundtablePlaybook,
  renderDoctrineLine,
  renderDoctrineLineForPlaybook,
  renderDoctrineLines,
  renderDoctrineLinesForPlaybook
} from "./legendary-investor-doctrines.mjs";

export function analyzeTradingPlan(planInput, { playbookOverride } = {}) {
  const text = String(planInput || "");
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const stockRules = parseStockRules(lines);
  const signals = derivePlanSignals(text);
  const primaryLeg =
    matchPlanLeg(text, [/([\p{Script=Han}A-Za-z0-9·]+)主腿/u, /([^\n,，。;；]+?)main leg/i], "") ||
    inferLegFromLines(lines, [/主做/u, /第一优先是/u, /主腿/u], "主腿") ||
    "主腿";
  const hedgeLeg =
    matchPlanLeg(text, [/([\p{Script=Han}A-Za-z0-9·]+)对冲腿/u, /([^\n,，。;；]+?)hedge/i], "") ||
    inferLegFromLines(lines, [/对冲优先是/u, /担心消息反转.*加/u, /对冲腿/u, /hedge/i], "对冲腿") ||
    "对冲腿";
  const confirmLeg =
    matchPlanLeg(text, [/([\p{Script=Han}A-Za-z0-9·]+)弹性腿/u], "") ||
    inferLegFromLines(lines, [/弹性选/u, /第二优先才是/u, /弹性腿/u, /确认后/u], "确认腿") ||
    matchConfirmLeg(text) ||
    "确认腿";

  const scenarioLabel = inferScenarioLabel(signals, text);
  const singleMentor = chooseSingleMentor(signals, text);
  const singleMentorReason = describeSingleMentorReason(singleMentor);
  const roundtablePlaybook = playbookOverride
    ? resolvePlaybookOverride(playbookOverride)
    : chooseRoundtablePlaybook(signals, text);
  const normalizedLegs = normalizeFallbackLegLabels(
    {
      primaryLeg,
      hedgeLeg,
      confirmLeg
    },
    roundtablePlaybook.key
  );
  const playbookRiskStrings = buildPlaybookRiskStrings(normalizedLegs, roundtablePlaybook.key);

  return {
    primaryLeg: normalizedLegs.primaryLeg,
    hedgeLeg: normalizedLegs.hedgeLeg,
    confirmLeg: normalizedLegs.confirmLeg,
    stockRules,
    signals,
    scenarioLabel,
    singleMentor,
    singleMentorReason,
    roundtablePlaybookKey: roundtablePlaybook.key,
    roundtablePlaybookLabel: roundtablePlaybook.label,
    roundtableMentors: roundtablePlaybook.mentors,
    roundtableRationale: roundtablePlaybook.rationale,
    planText: text,
    primaryRisk: `${normalizedLegs.confirmLeg} 在没有确认时被放大`,
    reversalRisk: playbookRiskStrings.reversalRisk,
    invalidTrigger: playbookRiskStrings.invalidTrigger,
    changeMindTrigger: playbookRiskStrings.changeMindTrigger
  };
}

export function buildLegendaryStageFallback(stage, planInput, priorResults = [], stageNotes = []) {
  const summary = analyzeTradingPlan(planInput);
  const noteTitles = stageNotes.map((note) => note.title).join(", ");
  const primaryRule = summary.stockRules?.[summary.primaryLeg] || null;
  const hedgeRule = summary.stockRules?.[summary.hedgeLeg] || null;
  const confirmRule = summary.stockRules?.[summary.confirmLeg] || null;
  const signals = summary.signals;
  const roundtable = buildRoundtableCommittee(summary, {
    primaryRule,
    hedgeRule,
    confirmRule
  });

  switch (stage.key) {
    case "workbench_v3":
      if (summary.roundtablePlaybookKey === "valuation_quality") {
        return [
          `本地后备模式：当前更像 ${summary.scenarioLabel}。`,
          "",
          `- 状态判断：这是质量与估值判断，不是事件溢价交易；当前更重要的是企业质量是否真实、价格是否给足赔率、长期语言是否被滥用。`,
          `- 工作流路径：先做质量与估值核验，再做赔率批判，再让 ${summary.singleMentor} 定持有纪律，再让 ${summary.roundtablePlaybookLabel} 决定是观察、分批还是等待更好价格。`,
          `- 当前最佳表达：${summary.primaryLeg} 先行，${summary.hedgeLeg} 用来约束出手节奏，${summary.confirmLeg} 只有在赔率改善后才上桌。`,
          `- 核心标的原则：${summary.primaryLeg} 只有在你离开短期故事也愿意继续持有时，才配进入主观察位。`,
          `- 加仓纪律：${summary.confirmLeg} 只有在估值更合理或质量证据继续强化后，才允许提高权重。`,
          `- 防守职责：${summary.hedgeLeg} 不是替高估值找理由，而是防止你在证据不足时过早重仓。`,
          `- 工作台依据：${noteTitles || "Workbench core notes"}。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "macro_reflexive") {
        return [
          `本地后备模式：当前更像 ${summary.scenarioLabel}。`,
          "",
          `- 状态判断：这是宏观传导与反身性判断，不是单票静态估值问题；更关键的是流动性、利率、美元、风险偏好是否形成同向链条。`,
          `- 工作流路径：先核验跨资产与流动性，再做赔率批判，再让 ${summary.singleMentor} 定传导链，再让 ${summary.roundtablePlaybookLabel} 决定结构。`,
          `- 当前最佳表达：${summary.primaryLeg} 先行，${summary.confirmLeg} 后置，${summary.hedgeLeg} 负责处理链条背离。`,
          `- 核心表达原则：${summary.primaryLeg} 只有在宏观变量与价格方向同向验证时，才配进入主结构。`,
          `- 加仓纪律：${summary.confirmLeg} 只有在跨资产确认同步后，才允许提高权重。`,
          `- 防守职责：${summary.hedgeLeg} 用于处理共振失灵，不是替主观叙事背书。`,
          `- 工作台依据：${noteTitles || "Workbench core notes"}。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "supply_demand_cycle") {
        return [
          `本地后备模式：当前更像 ${summary.scenarioLabel}。`,
          "",
          `- 状态判断：这是涨价与供需验证问题，不是单纯 headline 交易；更关键的是涨价是否落地、供给是否持续紧张、景气是否继续强化。`,
          `- 工作流路径：先核验涨价与供给事实，再做风险预算，再让 ${summary.singleMentor} 定执行，再让 ${summary.roundtablePlaybookLabel} 决定第二笔是 ${summary.confirmLeg} 还是 ${summary.hedgeLeg}。`,
          `- 当前最佳表达：${summary.primaryLeg} 主腿，${summary.confirmLeg} 弹性腿但后置，${summary.hedgeLeg} 防守腿。`,
          primaryRule
            ? `- 主腿交易卡：${summary.primaryLeg} 主题入场 ${primaryRule.themeEntry}，确认入场 ${primaryRule.confirmEntry}，失效 ${primaryRule.invalidation}。`
            : `- 主腿优先：${summary.primaryLeg}。`,
          confirmRule
            ? `- 弹性腿纪律：${summary.confirmLeg} 只有在 ${confirmRule.confirmEntry} 这类确认出现后才允许上桌。`
            : `- 弹性腿纪律：${summary.confirmLeg} 需要更强景气确认。`,
          hedgeRule
            ? `- 防守腿职责：${summary.hedgeLeg} 的作用是处理涨价不及预期、供给修复、或高景气证据开始走弱。`
            : `- 防守腿职责：${summary.hedgeLeg} 优先承担景气回落时的防守表达。`,
          `- 工作台依据：${noteTitles || "Workbench core notes"}。`
        ].join("\n");
      }
      return [
        `本地后备模式：当前更像 ${summary.scenarioLabel}。`,
        "",
        `- 状态判断：${signals.noAgreement ? "无协议仍成立" : "无协议未确认"}；${signals.noSubstantiveProgress ? "没有实质性续谈突破" : "续谈突破未知"}；${signals.notTotalBreak ? "不是彻底破裂" : "破裂程度待确认"}。`,
        `- 工作流路径：先做事实核验，再做风险审问，再让 ${summary.singleMentor} 定执行，再让圆桌决定第二笔是 ${summary.confirmLeg} 还是 ${summary.hedgeLeg}。`,
        `- 当前最佳表达：${summary.primaryLeg} 主腿，${summary.confirmLeg} 弹性腿但后置，${summary.hedgeLeg} 对冲腿。`,
        primaryRule
          ? `- 主腿交易卡：${summary.primaryLeg} 主题入场 ${primaryRule.themeEntry}，确认入场 ${primaryRule.confirmEntry}，失效 ${primaryRule.invalidation}。`
          : `- 主腿优先：${summary.primaryLeg}。`,
        confirmRule
          ? `- 弹性腿纪律：${summary.confirmLeg} 只有在 ${confirmRule.confirmEntry} 这类确认出现后才允许上桌。`
          : `- 弹性腿纪律：${summary.confirmLeg} 不确认不做。`,
        hedgeRule
          ? `- 对冲腿职责：${summary.hedgeLeg} 不是装饰仓，它的作用是吸收 headline 反转和风险溢价回落。`
          : `- 对冲腿职责：${summary.hedgeLeg} 优先承担防守表达。`,
        `- 工作台依据：${noteTitles || "Workbench core notes"}。`
      ].join("\n");
    case "critic_mode":
      if (summary.roundtablePlaybookKey === "valuation_quality") {
        return [
          ...buildCriticOpeners(summary),
          `最弱的假设是：你把高质量误当成任何价格都值得买。`,
          `最脆弱的腿是：${summary.confirmLeg}。它最容易在赔率没有改善时被提前放大。`,
          `最可能的错配是：你用长期语言替当前价格背书，或者用护城河掩盖它已经不便宜。`,
          `必须降级的动作：没有更好价格前，不把观察仓升级成正式仓；没有企业质量证据前，不把故事包装成护城河。`,
          `批判式结论：当前不是证明信仰的环境，而是等待质量与赔率同时站在你这边的环境。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "macro_reflexive") {
        return [
          ...buildCriticOpeners(summary),
          `最弱的假设是：你把单一宏观叙事误当成跨资产共识。`,
          `最脆弱的腿是：${summary.confirmLeg}。它最容易在共振未形成时被提前放大。`,
          `最可能的错配是：流动性、利率、美元没有同向验证，你却先给了方向性重仓。`,
          `必须降级的动作：没有跨资产确认前，不把观察仓升级成正式仓；没有赔率前，不把宏观故事当执行许可。`,
          `批判式结论：当前不是单看一个变量就全押的环境，而是等待传导链和价格共振都出现的环境。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "supply_demand_cycle") {
        return [
          ...buildCriticOpeners(summary),
          `最弱的假设是：你把涨价预期当成了涨价兑现。`,
          `最脆弱的腿是：${summary.confirmLeg}。它最依赖景气继续强化，也最容易在供给修复时被先杀。`,
          `最可能的错配是：你看到产业链热度就提前放大 ${summary.confirmLeg}，却没有拿到排产、稼动率、价格传导的更强证据。`,
          `必须降级的动作：没有涨价落地或高景气确认前，不把观察仓升级成正式仓；没有供需继续收紧证据前，不把景气故事当成执行许可。`,
          `批判式结论：当前不是“只要会涨价就都能做”的环境，而是“先做定价权更强、验证更硬的主腿，再等弹性腿确认”的环境。`
        ].join("\n");
      }
      return [
        ...buildCriticOpeners(summary),
        `最弱的假设是：${summary.primaryRisk}。`,
        `最脆弱的腿是：${summary.confirmLeg}。它最依赖风险溢价继续扩张，也最容易被缓和 headline 反杀。`,
        `最可能的错配是：计划里的确信度高于可验证证据，尤其当你想提前放大 ${summary.confirmLeg} 或高开追价时。`,
        `必须降级的动作：没有确认前，不把观察仓升级成正式仓；没有新增事实前，不把“无协议”脑补成“继续升级”。`,
        `批判式结论：当前不是“油运默认第二优先”的环境，而是“主腿先行、对冲可先于弹性”的环境。`
      ].join("\n");
    case "single_mentor":
      return buildSingleMentorStage(summary, primaryRule, confirmRule);
    case "roundtable":
      return [
        `- 委员会类型：${summary.roundtablePlaybookLabel}。`,
        `- 路由原因：${summary.roundtableRationale}`,
        `- 委员会票型：${roundtable.supportCount} 支持 / ${roundtable.conditionalCount} 有条件支持 / ${roundtable.opposeCount} 反对。`,
        "",
        renderRoundtableVoteTable(roundtable.cards),
        "",
        `- 委员会组合上限：${roundtable.committeeMaxPosition}。`,
        `- 默认结构：${roundtable.verdict.defaultStructure}`,
        `- 升级路径：${roundtable.verdict.upgradePath}`,
        `- 降级顺序：${roundtable.verdict.downgradeSequence}`,
        `- 禁止动作：${roundtable.verdict.doNotDo}`,
        `- 共识：${roundtable.consensus}`,
        `- 分歧：${roundtable.disagreement}`,
        `- 主方案：${roundtable.primaryPlan}`,
        `- 备选方案：${roundtable.backupPlan}`,
        `- 改票条件：${roundtable.changeMind}`,
        ...roundtable.cards.map((card) => `- ${card.mentor} stance: ${card.stance}`),
        ...roundtable.cards.map((card) => `- ${card.mentor} key evidence: ${card.keyEvidence}`),
        ...roundtable.cards.map((card) => `- ${card.mentor} kill switch: ${card.killSwitch}`)
      ].join("\n");
    case "trade_review":
      if (summary.roundtablePlaybookKey === "valuation_quality") {
        return [
          `- ${renderDoctrineLine("Howard Marks", "reviewPrompt", summary)}`,
          `- ${renderDoctrineLine("Hard Lessons", "reviewPrompt", summary)}`,
        `- ${renderDoctrineLineForPlaybook(summary.singleMentor, "reviewPrompt", summary.roundtablePlaybookKey, { ...summary, confirmEntry: confirmRule?.confirmEntry || "确认条件" }, `${summary.singleMentor} 式复盘会盯住：你有没有在质量证据没变强前，就先提高了 ${summary.confirmLeg} 的权重。`)}`,
          `- 最可能的错误：在赔率没有改善时提前放大 ${summary.confirmLeg}。`,
          `- 盘中必须记录：你的估值假设、你离开短期故事是否还愿意持有、${summary.hedgeLeg} 是否只是替高估值找理由。`,
          `- 收盘后必须复核：${summary.primaryLeg} 是否真配长期持有，${summary.hedgeLeg} 是否防止了过早出手，${summary.confirmLeg} 是否只是情绪加仓。`,
          `- If-Then 规则：`,
          `  1. If 你说不出为什么离开短期故事还愿意持有, then 视为交易而非投资。`,
          `  2. If 价格更贵但质量证据没变强, then 不加 ${summary.confirmLeg}。`,
          `  3. If 你用长期语言掩盖当前高价, then 视为 thesis 污染。`,
          `  4. If ${summary.hedgeLeg} 只是让你更敢追高, then 说明防守设计失败。`,
          `  5. If 盘后复盘写不出更好赔率区间, then 下次只能观察。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "macro_reflexive") {
        return [
          `- ${renderDoctrineLine("Howard Marks", "reviewPrompt", summary)}`,
          `- ${renderDoctrineLine("Hard Lessons", "reviewPrompt", summary)}`,
        `- ${renderDoctrineLineForPlaybook(summary.singleMentor, "reviewPrompt", summary.roundtablePlaybookKey, { ...summary, confirmEntry: confirmRule?.confirmEntry || "确认条件" }, `${summary.singleMentor} 式复盘会盯住：你有没有在跨资产没有共振前，就先提高了 ${summary.confirmLeg} 的权重。`)}`,
          `- 最可能的错误：在传导链没有闭环时提前放大 ${summary.confirmLeg}。`,
          `- 盘中必须记录：流动性、利率、美元、风险偏好是否同向；${summary.hedgeLeg} 是否真的处理了链条背离。`,
          `- 收盘后必须复核：${summary.primaryLeg} 是否仍被跨资产确认，${summary.hedgeLeg} 是否有效，${summary.confirmLeg} 是否只是叙事加仓。`,
          `- If-Then 规则：`,
          `  1. If 没有跨资产确认, then 不加 ${summary.confirmLeg}。`,
          `  2. If 关键宏观变量开始背离, then 先缩 ${summary.confirmLeg}。`,
          `  3. If 你说不清传导链如何闭环, then 视为叙事污染。`,
          `  4. If ${summary.hedgeLeg} 没有吸收链条背离, then 说明结构设计失败。`,
          `  5. If 盘后复盘写不出哪个变量最关键, then 下次仓位自动降级。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "supply_demand_cycle") {
        return [
          `- ${renderDoctrineLine("Howard Marks", "reviewPrompt", summary)}`,
          `- ${renderDoctrineLine("Hard Lessons", "reviewPrompt", summary)}`,
          `- ${renderDoctrineLineForPlaybook(summary.singleMentor, "reviewPrompt", summary.roundtablePlaybookKey, { ...summary, confirmEntry: confirmRule?.confirmEntry || "确认条件" }, `${summary.singleMentor} 式复盘会盯住：你有没有在涨价兑现或景气确认前，就先提高了 ${summary.confirmLeg} 的权重。`)}`,
          `- 最可能的错误：在涨价还停留在预期层时提前放大 ${summary.confirmLeg}。`,
          `- 盘中必须记录：涨价是否落地、供给是否继续紧张、排产/稼动率是否强化、${summary.hedgeLeg} 是否真的起到了防守作用。`,
          `- 收盘后必须复核：${summary.primaryLeg} 是否仍是定价权和验证最强的主腿，${summary.hedgeLeg} 是否有效，${summary.confirmLeg} 是否只是情绪加仓。`,
          `- If-Then 规则：`,
          `  1. If 没有新增涨价或供需确认, then 不加 ${summary.confirmLeg}。`,
          `  2. If 供给修复快于预期, then 先缩 ${summary.confirmLeg}。`,
          `  3. If 主腿强但弹性腿不跟, then 说明资金不认可第二层弹性。`,
          `  4. If ${summary.hedgeLeg} 没有在景气回落时保护结构, then 说明防守设计失败。`,
          `  5. If 盘后复盘写不出哪条供需证据最关键, then 下次仓位自动降级。`
        ].join("\n");
      }
      return [
        `- ${renderDoctrineLine("Howard Marks", "reviewPrompt", summary)}`,
        `- ${renderDoctrineLine("Hard Lessons", "reviewPrompt", summary)}`,
        `- ${renderDoctrineLineForPlaybook(summary.singleMentor, "reviewPrompt", summary.roundtablePlaybookKey, { ...summary, confirmEntry: confirmRule?.confirmEntry || "确认条件" }, `${summary.singleMentor} 式复盘会盯住：你有没有在 ${confirmRule?.confirmEntry || "确认条件"} 出现前就先给了 ${summary.confirmLeg} 过高仓位。`)}`,
        `- 最可能的错误：在确认不足时提前放大 ${summary.confirmLeg}。`,
        `- 盘中必须记录：最后一条 headline、加仓前是否有确认、对冲腿是否真的对冲。`,
        `- 收盘后必须复核：${summary.primaryLeg} 是否真是最稳定主腿，${summary.hedgeLeg} 是否有效，${summary.confirmLeg} 是否只是追价。`,
        `- If-Then 规则：`,
        `  1. If 没有新增确认, then 不加 ${summary.confirmLeg}。`,
        `  2. If 出现缓和 headline, then 先缩 ${summary.confirmLeg}。`,
        `  3. If 主腿走弱但对冲腿走强, then 降总风险暴露。`,
        `  4. If 你说不清交易事实, then 视为脑补升级。`,
        `  5. If 盘后复盘无法写出失效条件, then 下次仓位自动降级。`
      ].join("\n");
    case "final_action_card":
      if (summary.roundtablePlaybookKey === "valuation_quality") {
        return [
          `- 盘前核验：核验企业质量、核验资本配置、核验现金流质量、核验当前价格是否仍有赔率。`,
          `- Open conditions: 先看 ${summary.primaryLeg} 的质量与价格，再看 ${summary.hedgeLeg}，最后看 ${summary.confirmLeg}。`,
          `- 委员会上限：${roundtable.committeeMaxPosition}。`,
          `- 默认结构：${roundtable.verdict.defaultStructure}`,
          `- 升级路径：${roundtable.verdict.upgradePath}`,
          `- 降级顺序：${roundtable.verdict.downgradeSequence}`,
          `- 核心标的卡：只有当你离开短期故事也愿意继续持有时，${summary.primaryLeg} 才配提高权重。`,
          `- 加仓卡：${summary.confirmLeg} 只有在更好价格或质量证据继续强化后才可加。`,
          `- 防守卡：${summary.hedgeLeg} 的职责是防止你在高估值阶段过早重仓，不是替追价找理由。`,
          `- 哲学备注：这不是拿长期口号覆盖当前价格的环境。`,
          `- Do-not-chase rules: 没有更好价格不追，质量没变强也不追，不要用长期语言掩盖坏赔率。`,
          `- Downgrade trigger: 估值继续扩张但质量证据没有同步变强。`,
          `- Invalidation trigger: 你发现自己离开短期故事就不愿持有，或企业质量判断被证伪。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "macro_reflexive") {
        return [
          `- 盘前核验：核验流动性、核验利率与美元、核验风险偏好、核验跨资产是否共振。`,
          `- Open conditions: 先看 ${summary.primaryLeg}，再看 ${summary.hedgeLeg}，最后看 ${summary.confirmLeg}。`,
          `- 委员会上限：${roundtable.committeeMaxPosition}。`,
          `- 默认结构：${roundtable.verdict.defaultStructure}`,
          `- 升级路径：${roundtable.verdict.upgradePath}`,
          `- 降级顺序：${roundtable.verdict.downgradeSequence}`,
          `- 核心表达卡：只有当宏观变量与价格方向形成同向验证时，${summary.primaryLeg} 才配提高权重。`,
          `- 加仓卡：${summary.confirmLeg} 只有在跨资产共振同步后才可加。`,
          `- 防守卡：${summary.hedgeLeg} 的职责是处理传导链背离，不是替主观叙事背书。`,
          `- 哲学备注：没有传导链闭环，就没有资格给方向性重仓。`,
          `- Do-not-chase rules: 没有跨资产确认不追，没有传导链闭环不加。`,
          `- Downgrade trigger: 跨资产开始分化或关键变量背离。`,
          `- Invalidation trigger: 宏观传导链断裂，或价格方向失去跨资产验证。`
        ].join("\n");
      }
      if (summary.roundtablePlaybookKey === "supply_demand_cycle") {
        return [
          `- 盘前核验：核验涨价消息、核验供给是否继续紧张、核验排产/稼动率、核验主腿和弹性腿是否同步得到景气确认。`,
          `- Open conditions: 先看 ${summary.primaryLeg}，再看 ${summary.hedgeLeg}，最后看 ${summary.confirmLeg}。`,
          `- 委员会上限：${roundtable.committeeMaxPosition}。`,
          `- 默认结构：${roundtable.verdict.defaultStructure}`,
          `- 升级路径：${roundtable.verdict.upgradePath}`,
          `- 降级顺序：${roundtable.verdict.downgradeSequence}`,
          primaryRule
            ? `- 主腿卡：${summary.primaryLeg} 主题入场 ${primaryRule.themeEntry}，确认 ${primaryRule.confirmEntry}，失效 ${primaryRule.invalidation}。`
            : `- 主腿卡：${summary.primaryLeg} 先做验证最强的定价权主腿。`,
          confirmRule
            ? `- 弹性卡：${summary.confirmLeg} 只有在 ${confirmRule.confirmEntry} 这种景气确认出现后才可加。`
            : `- 弹性卡：${summary.confirmLeg} 没有景气确认不追。`,
          hedgeRule
            ? `- 防守卡：${summary.hedgeLeg} 的职责是处理涨价不及预期、供给修复、或景气走弱。`
            : `- 防守卡：${summary.hedgeLeg} 优先承担景气回落时的防守表达。`,
          `- 哲学备注：这不是“看到涨价题材就全面进攻”的环境，必须看到定价权与供需证据继续站在你这边。`,
          `- Do-not-chase rules: ${summary.confirmLeg} 不确认不追，主腿离确认位太远也不追。`,
          `- Downgrade trigger: ${summary.reversalRisk}。`,
          `- Invalidation trigger: ${summary.invalidTrigger}。`
        ].join("\n");
      }
      return [
        `- Monday pre-open checklist: 核验 headline、核验主腿、核验对冲腿、核验确认腿。`,
        `- Open conditions: 先看 ${summary.primaryLeg}，再看 ${summary.hedgeLeg}，最后看 ${summary.confirmLeg}。`,
        `- 委员会上限：${roundtable.committeeMaxPosition}。`,
        `- 默认结构：${roundtable.verdict.defaultStructure}`,
        `- 升级路径：${roundtable.verdict.upgradePath}`,
        `- 降级顺序：${roundtable.verdict.downgradeSequence}`,
        primaryRule
          ? `- 主腿卡：${summary.primaryLeg} 主题入场 ${primaryRule.themeEntry}，确认 ${primaryRule.confirmEntry}，失效 ${primaryRule.invalidation}。`
          : `- 主腿卡：${summary.primaryLeg} 先主题入场，再等确认。`,
        confirmRule
          ? `- 弹性卡：${summary.confirmLeg} 只有在 ${confirmRule.confirmEntry} 这种确认出现后才可加。`
          : `- 弹性卡：${summary.confirmLeg} 不确认不追。`,
        hedgeRule
          ? `- 对冲卡：${summary.hedgeLeg} 的职责是处理反转，不是替主腿背锅。`
          : `- 对冲卡：${summary.hedgeLeg} 优先承担防守表达。`,
        `- ${renderDoctrineLineForPlaybook("Howard Marks", "actionCardNote", summary.roundtablePlaybookKey, summary)}`,
        `- Do-not-chase rules: ${summary.confirmLeg} 不确认不追，主腿离确认位太远也不追。`,
        `- Downgrade trigger: ${summary.reversalRisk}。`,
        `- Invalidation trigger: ${summary.invalidTrigger}。`
      ].join("\n");
    default:
      return `本地后备模式：${stage.title} 暂无专用模板。`;
  }
}

function buildSingleMentorStage(summary, primaryRule, confirmRule) {
  const doctrine = getLegendaryDoctrine(summary.singleMentor);
  const lines = [
    `最佳单导师：${summary.singleMentor}。`,
    `原因：这份计划最需要的是 ${doctrine?.fitReason || summary.singleMentorReason}。`,
    ""
  ];

  lines.push(
    `- ${renderDoctrineLineForPlaybook(summary.singleMentor, "singleMentorLead", summary.roundtablePlaybookKey, summary, `${summary.singleMentor} 会先用自己的框架重写你的交易。`)}`
  );
  lines.push(
    `- ${renderDoctrineLineForPlaybook(summary.singleMentor, "singleMentorBelief", summary.roundtablePlaybookKey, summary, "核心认知：先做最能被事实和赔率同时支持的那条腿。")}`
  );

  lines.push(`- Trade: 优先 ${summary.primaryLeg}，其次 ${summary.hedgeLeg}，${summary.confirmLeg} 只确认后做。`);
  lines.push(
    primaryRule
      ? `- Entry discipline: ${summary.primaryLeg} 先看 ${primaryRule.themeEntry}，真正加码要等 ${primaryRule.confirmEntry}。`
      : `- Entry discipline: 主腿先主题入场，再确认入场。`
  );
  lines.push(
    confirmRule
      ? `- Confirmation discipline: ${summary.confirmLeg} 不到 ${confirmRule.confirmEntry} 不上量。`
      : `- Confirmation discipline: ${summary.confirmLeg} 不确认不追。`
  );
  lines.push(`- Sizing: 让主腿承载方向，让对冲腿承载 headline 反转风险，让确认腿承载弹性。`);
  lines.push(`- Invalidation: 一旦 ${summary.invalidTrigger}，先缩 ${summary.confirmLeg}，再重看主腿。`);
  lines.push(`- What not to do: 不要把“脑补升级”误当成“事实升级”。`);

  return lines.join("\n");
}

export function buildRoundtableCommittee(summary, options = {}) {
  const primaryRule = options.primaryRule || summary.stockRules?.[summary.primaryLeg] || null;
  const hedgeRule = options.hedgeRule || summary.stockRules?.[summary.hedgeLeg] || null;
  const confirmRule = options.confirmRule || summary.stockRules?.[summary.confirmLeg] || null;
  const cards = buildRoundtableVoteCards(summary, {
    primaryRule,
    hedgeRule,
    confirmRule
  });
  const supportCount = cards.filter((card) => card.vote === "support").length;
  const conditionalCount = cards.filter((card) => card.vote === "conditional").length;
  const opposeCount = cards.filter((card) => card.vote === "oppose").length;
  const verdict = buildCommitteeVerdict(summary, cards, {
    primaryRule,
    hedgeRule,
    confirmRule
  });

  return {
    cards,
    supportCount,
    conditionalCount,
    opposeCount,
    verdict,
    committeeMaxPosition:
      buildCommitteeMaxPosition(cards, [
        summary.primaryLeg,
        summary.hedgeLeg,
        summary.confirmLeg
      ]) || "以最保守导师上限为准",
    consensus: `${summary.primaryLeg} 是委员会共同主腿，${summary.hedgeLeg} 是第二层防守，${summary.confirmLeg} 只在确认后参与。`,
    disagreement: `主要分歧不在是否做 ${summary.primaryLeg}，而在是否要提前提高 ${summary.confirmLeg} 的权重。`,
    primaryPlan: `${summary.primaryLeg} -> ${summary.hedgeLeg} -> ${summary.confirmLeg}${confirmRule ? `（仅在 ${confirmRule.confirmEntry} 后）` : "（仅确认后）"}`,
    backupPlan: `如果 ${summary.reversalRisk}，先降级为 ${summary.primaryLeg} + ${summary.hedgeLeg}；如果主腿也失守，只留 ${summary.hedgeLeg} 或转观察。`,
    changeMind: buildCommitteeChangeMind(summary, cards)
  };
}

export function buildRoundtableVoteCards(summary, options = {}) {
  const primaryRule = options.primaryRule || summary.stockRules?.[summary.primaryLeg] || null;
  const hedgeRule = options.hedgeRule || summary.stockRules?.[summary.hedgeLeg] || null;
  const confirmRule = options.confirmRule || summary.stockRules?.[summary.confirmLeg] || null;

  const mentors = Array.isArray(summary.roundtableMentors) && summary.roundtableMentors.length > 0
    ? summary.roundtableMentors
    : ROUNDTABLE_MENTORS;

  return mentors.map((mentor) =>
    buildRoundtableVoteCard(mentor, summary, {
      primaryRule,
      hedgeRule,
      confirmRule
    })
  );
}

function inferScenarioLabel(signals, text) {
  if (signals.noAgreement && signals.riskNotReleased && signals.noSubstantiveProgress) {
    return "事件驱动交易工作台";
  }
  if (signals.priceHike || signals.supplyShortage || signals.highUtilization || signals.electronicCloth) {
    return "供需周期交易工作台";
  }
  if (/价值|估值|护城河|五年持有|长期持有/.test(text)) {
    return "多导师投资决策工作台";
  }
  return "多导师交易决策工作台";
}

function chooseSingleMentor(signals, text) {
  if (/估值|护城河|五年持有|资本配置|现金流/.test(text)) {
    return "Buffett";
  }
  if (/定价权|提价能力|成本转嫁/.test(text)) {
    return "Buffett";
  }
  if (signals.priceHike || signals.supplyShortage || signals.highUtilization || signals.electronicCloth) {
    return "Druckenmiller";
  }
  if (/Brent|黄金|霍尔木兹|headline|无协议|风险未解除|确认入场|放量/.test(text)) {
    return "Druckenmiller";
  }
  if (signals.riskNotReleased || signals.oilTransportFragile) {
    return "Druckenmiller";
  }
  return "Howard Marks";
}

function resolvePlaybookOverride(key) {
  return getLegendaryRoundtablePlaybook(key);
}

function chooseRoundtablePlaybook(signals, text) {
  const value = String(text || "");
  if (/估值|护城河|五年持有|长期持有|资本配置|现金流|自由现金流|ROE|护城河/.test(value)) {
    return getLegendaryRoundtablePlaybook("valuation_quality");
  }
  if (/流动性|风险偏好|跨资产|美元|收益率|利率|宏观|反身性/.test(value)) {
    return getLegendaryRoundtablePlaybook("macro_reflexive");
  }
  if (
    signals.priceHike ||
    signals.supplyShortage ||
    signals.highUtilization ||
    signals.electronicCloth ||
    /涨价|提价|供不应求|供应紧缺|景气|稼动率|缺货|限产|产能紧张|满产|满负荷/.test(value)
  ) {
    return getLegendaryRoundtablePlaybook("supply_demand_cycle");
  }
  if (
    signals.noAgreement ||
    signals.riskNotReleased ||
    /Brent|黄金|霍尔木兹|headline|确认入场|放量/.test(value)
  ) {
    return getLegendaryRoundtablePlaybook("event_driven_risk");
  }
  return getLegendaryRoundtablePlaybook("event_driven_risk");
}

function normalizeFallbackLegLabels(legs, playbookKey) {
  const current = {
    primaryLeg: legs.primaryLeg,
    hedgeLeg: legs.hedgeLeg,
    confirmLeg: legs.confirmLeg
  };
  const isDefaultPlaceholder =
    current.primaryLeg === "主腿" &&
    current.hedgeLeg === "对冲腿" &&
    current.confirmLeg === "确认腿";

  if (!isDefaultPlaceholder) {
    return current;
  }

  switch (playbookKey) {
    case "valuation_quality":
      return {
        primaryLeg: "核心标的",
        hedgeLeg: "防守仓",
        confirmLeg: "加仓位"
      };
    case "macro_reflexive":
      return {
        primaryLeg: "核心表达",
        hedgeLeg: "防守表达",
        confirmLeg: "加仓位"
      };
    default:
      return current;
  }
}

function describeSingleMentorReason(mentor) {
  switch (mentor) {
    case "Druckenmiller":
      return "仓位、确认、风险切换和认错速度";
    case "Howard Marks":
      return "中间态判断、风险预算和错配识别";
    case "Dalio":
      return "流动性、风险溢价和跨资产链条";
    default:
      return "风险识别和执行排序";
  }
}

function buildCriticOpeners(summary) {
  const mentors = Array.isArray(summary.roundtableMentors) && summary.roundtableMentors.length > 0
    ? summary.roundtableMentors
    : ["Druckenmiller", "Howard Marks"];

  return mentors.flatMap((mentor) =>
    renderDoctrineLinesForPlaybook(mentor, "criticOpeners", summary.roundtablePlaybookKey, summary)
  );
}

function buildPlaybookRiskStrings(legs, playbookKey) {
  switch (playbookKey) {
    case "valuation_quality":
      return {
        reversalRisk: "价格继续扩张但质量证据没有同步变强",
        invalidTrigger: `你发现自己离开短期故事就不愿继续持有 ${legs.primaryLeg}，或 ${legs.confirmLeg} 只是情绪加仓`,
        changeMindTrigger: `${legs.primaryLeg}、估值纪律、持有意愿三者出现明显背离`
      };
    case "supply_demand_cycle":
      return {
        reversalRisk: "涨价不及预期、供给修复快于预期、或高景气证据开始走弱",
        invalidTrigger: `${legs.primaryLeg} 失去涨价或供需验证，同时 ${legs.confirmLeg} 无法证明景气继续强化`,
        changeMindTrigger: `${legs.primaryLeg}、${legs.hedgeLeg}、产业链供需信号三者出现明显背离`
      };
    case "macro_reflexive":
      return {
        reversalRisk: "跨资产共振失灵或关键宏观变量开始背离",
        invalidTrigger: `${legs.primaryLeg} 失去跨资产验证，同时 ${legs.confirmLeg} 无法证明传导链继续强化`,
        changeMindTrigger: `${legs.primaryLeg}、${legs.hedgeLeg}、关键宏观变量三者出现明显背离`
      };
    default:
      return {
        reversalRisk: "出现缓和 headline 或主线资产高开后快速回落",
        invalidTrigger: `${legs.primaryLeg} 失守关键条件，同时 ${legs.confirmLeg} 无法自证强化`,
        changeMindTrigger: `headline、${legs.primaryLeg}、${legs.hedgeLeg} 三者出现明显背离`
      };
  }
}

function buildRoundtableVoteCard(mentor, summary, rules) {
  const confidence = scoreRoundtableConfidence(mentor, summary, rules);

  return {
    mentor,
    vote: decideRoundtableVote(mentor, summary, rules),
    confidence,
    confidenceLabel: `${confidence}/100`,
    maxPosition: renderDoctrineLine(
      mentor,
      "maxPositionGuidance",
      summary,
      `${summary.primaryLeg} 0.40 / ${summary.hedgeLeg} 0.20 / ${summary.confirmLeg} 0.10`
    ),
    keyEvidence: renderDoctrineLineForPlaybook(
      mentor,
      "evidenceFocus",
      summary.roundtablePlaybookKey,
      summary,
      `${summary.primaryLeg} 的映射更直接，${summary.hedgeLeg} 负责防反转，${summary.confirmLeg} 只做确认仓。`
    ),
    killSwitch: renderDoctrineLineForPlaybook(
      mentor,
      "killSwitchFocus",
      summary.roundtablePlaybookKey,
      summary,
      `${summary.changeMindTrigger} 时立即降级。`
    ),
    stance: renderDoctrineLineForPlaybook(
      mentor,
      "roundtableStance",
      summary.roundtablePlaybookKey,
      summary,
      `${mentor}：优先 ${summary.primaryLeg}，谨慎对待 ${summary.confirmLeg}。`
    )
  };
}

function decideRoundtableVote(mentor, summary, rules) {
  switch (mentor) {
    case "Druckenmiller":
      if (!rules.primaryRule) {
        return "conditional";
      }
      return rules.confirmRule ? "support" : "conditional";
    case "Howard Marks":
      if (!summary.signals.riskNotReleased) {
        return summary.roundtablePlaybookKey === "valuation_quality" ? "support" : "conditional";
      }
      return rules.hedgeRule ? "support" : "conditional";
    case "Dalio":
      if (summary.roundtablePlaybookKey === "macro_reflexive") {
        return "support";
      }
      if (!summary.signals.noAgreement || !summary.signals.riskNotReleased) {
        return "oppose";
      }
      return "conditional";
    case "Buffett":
      if (
        summary.roundtablePlaybookKey === "valuation_quality" ||
        summary.roundtablePlaybookKey === "supply_demand_cycle"
      ) {
        return "support";
      }
      return "conditional";
    case "GMO":
      if (summary.roundtablePlaybookKey === "valuation_quality") {
        return /太贵|高估|追高|估值/.test(summary.planText || "") ? "support" : "conditional";
      }
      return "conditional";
    default:
      return "conditional";
  }
}

function scoreRoundtableConfidence(mentor, summary, rules) {
  let score = 48;

  if (summary.signals.noAgreement) {
    score += 8;
  }
  if (summary.signals.riskNotReleased) {
    score += 8;
  }
  if (summary.signals.noSubstantiveProgress) {
    score += 4;
  }
  if (summary.signals.notTotalBreak) {
    score -= 2;
  }
  if (rules.primaryRule) {
    score += 4;
  }
  if (rules.hedgeRule) {
    score += 3;
  }
  if (rules.confirmRule) {
    score += 3;
  }
  if (summary.signals.reversalConcern) {
    score -= 2;
  }
  if (summary.signals.oilTransportFragile) {
    score -= 4;
  }
  if (summary.signals.priceHike) {
    score += 6;
  }
  if (summary.signals.supplyShortage) {
    score += 6;
  }
  if (summary.signals.highUtilization) {
    score += 4;
  }

  switch (mentor) {
    case "Druckenmiller":
      score += 4;
      if (!rules.confirmRule) {
        score -= 5;
      }
      break;
    case "Howard Marks":
      score += 2;
      if (!rules.hedgeRule) {
        score -= 4;
      }
      break;
    case "Dalio":
      score -= 4;
      if (rules.hedgeRule) {
        score += 2;
      }
      if (!summary.signals.noAgreement) {
        score -= 8;
      }
      break;
    case "Buffett":
      score += summary.roundtablePlaybookKey === "valuation_quality" ? 8 : -2;
      if (summary.roundtablePlaybookKey === "supply_demand_cycle") {
        score += 6;
      }
      if (/护城河|资本配置|现金流|五年持有|长期持有/.test(summary.planText || "")) {
        score += 6;
      }
      if (/定价权|提价能力|成本转嫁/.test(summary.planText || "")) {
        score += 4;
      }
      break;
    case "GMO":
      score += summary.roundtablePlaybookKey === "valuation_quality" ? 6 : 0;
      if (/估值|太贵|高估|追高|赔率/.test(summary.planText || "")) {
        score += 6;
      }
      break;
    default:
      break;
  }

  return clamp(Math.round(score), 35, 92);
}

function buildCommitteeMaxPosition(cards, orderedLegs) {
  const capByLeg = new Map();

  for (const card of cards) {
    if (card.vote === "oppose") {
      continue;
    }
    for (const entry of parsePositionGuidance(card.maxPosition)) {
      const current = capByLeg.get(entry.leg);
      if (current === undefined || entry.cap < current) {
        capByLeg.set(entry.leg, entry.cap);
      }
    }
  }

  return orderedLegs
    .filter((leg) => capByLeg.has(leg))
    .map((leg) => `${leg} ${capByLeg.get(leg).toFixed(2)}`)
    .join(" / ");
}

function buildCommitteeChangeMind(summary, cards) {
  const unique = new Set([summary.changeMindTrigger, ...cards.map((card) => card.killSwitch)]);
  return [...unique]
    .filter(Boolean)
    .map((item) => String(item).replace(/[。；\s]+$/g, "").trim())
    .slice(0, 3)
    .join("；");
}

function buildCommitteeVerdict(summary, cards, rules) {
  const confirmEntry = rules.confirmRule?.confirmEntry || "确认信号出现";
  const primaryCap = resolveLegCap(cards, summary.primaryLeg);
  const hedgeCap = resolveLegCap(cards, summary.hedgeLeg);
  const confirmCap = resolveLegCap(cards, summary.confirmLeg);
  const doNotDo = buildPlaybookDoNotDo(summary);

  return {
    defaultStructure: `${summary.primaryLeg}${primaryCap !== null ? ` ${primaryCap.toFixed(2)}` : ""} + ${summary.hedgeLeg}${hedgeCap !== null ? ` ${hedgeCap.toFixed(2)}` : ""}，${summary.confirmLeg} 默认后置`,
    upgradePath: `${summary.confirmLeg} 只有在 ${confirmEntry} 后，才允许升到第三腿${confirmCap !== null ? `，上限 ${confirmCap.toFixed(2)}` : ""}`,
    downgradeSequence: `先减 ${summary.confirmLeg}，再看 ${summary.primaryLeg} 是否还能守住主线；若 ${summary.reversalRisk}，只留 ${summary.hedgeLeg} 或转观察`,
    doNotDo,
    priorityOrder: [summary.primaryLeg, summary.hedgeLeg, summary.confirmLeg],
    defaultLegs: [summary.primaryLeg, summary.hedgeLeg],
    conditionalLegs: [summary.confirmLeg]
  };
}

function parsePositionGuidance(guidance) {
  return String(guidance || "")
    .split("/")
    .map((segment) => segment.trim())
    .map((segment) => {
      const match = segment.match(/^(.+?)\s+(\d+(?:\.\d+)?)$/);
      if (!match) {
        return null;
      }
      return {
        leg: match[1].trim(),
        cap: Number.parseFloat(match[2])
      };
    })
    .filter(Boolean);
}

function renderRoundtableVoteTable(cards) {
  return [
    "| Mentor | Vote | Confidence | Max Position |",
    "|---|---|---|---|",
    ...cards.map(
      (card) =>
        `| ${card.mentor} | ${formatVoteLabel(card.vote)} | ${card.confidenceLabel} | ${card.maxPosition} |`
    )
  ].join("\n");
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function resolveLegCap(cards, leg) {
  const caps = cards
    .filter((card) => card.vote !== "oppose")
    .flatMap((card) => parsePositionGuidance(card.maxPosition))
    .filter((entry) => entry.leg === leg)
    .map((entry) => entry.cap);

  if (caps.length === 0) {
    return null;
  }

  return Math.min(...caps);
}

function formatVoteLabel(vote) {
  switch (vote) {
    case "support":
      return "支持";
    case "conditional":
      return "有条件支持";
    case "oppose":
      return "反对";
    default:
      return vote;
  }
}

function buildPlaybookDoNotDo(summary) {
  switch (summary.roundtablePlaybookKey) {
    case "valuation_quality":
      return `不要把 ${summary.confirmLeg} 当前排到 ${summary.hedgeLeg} 前面；不要因为喜欢企业就忽略价格纪律；不要在更贵的价格上用长期语言为自己找理由`;
    case "supply_demand_cycle":
      return `不要把 ${summary.confirmLeg} 当前排到 ${summary.hedgeLeg} 前面；不要把“涨价预期”直接升级成“业绩兑现”；不要在供给修复信号出现后还把景气当成单边事实`;
    case "macro_reflexive":
      return `不要把 ${summary.confirmLeg} 当前排到 ${summary.hedgeLeg} 前面；不要在跨资产没有确认时先给方向性重仓；不要用单一宏观观点替代完整传导链`;
    default:
      return `不要把 ${summary.confirmLeg} 当前排到 ${summary.hedgeLeg} 前面；不要把“无协议”直接升级成“继续恶化”；不要在主腿远离确认位时追价`;
  }
}

function derivePlanSignals(text) {
  const value = String(text || "");
  return {
    noAgreement: /无协议/.test(value),
    noSubstantiveProgress: /没有实质性续谈突破|没有实质性突破|无实质性续谈突破/.test(value),
    riskNotReleased: /风险未解除|没有解除风险/.test(value),
    notTotalBreak: /不是彻底破裂/.test(value),
    reversalConcern: /担心消息反转|缓和 headline|缓和/.test(value),
    oilTransportFragile: /油运最容易被冲高回落误伤/.test(value),
    priceHike: /涨价|提价|价格上调|调价/.test(value),
    supplyShortage: /供不应求|供应紧缺|缺货|产能紧张/.test(value),
    highUtilization: /景气|稼动率|满产|满负荷|排产/.test(value),
    electronicCloth: /电子布|玻纤|覆铜板|CCL/.test(value),
    // Momentum / Wyckoff signals
    endStageAcceleration: /末端加速|加速赶顶|连续涨停后|连板后/.test(value),
    highConsensusChase: /一致性过高|高位一致|追涨|追高位/.test(value),
    volumeBreakout: /放量突破|量能突破|成交量放大突破/.test(value),
    falseBreakout: /假突破|冲高回落|虚破/.test(value),
    strongCloseUnchaseable: /强收盘但不可追|涨停但次日|强势收盘.*等分歧/.test(value),
  };
}

function parseStockRules(lines) {
  const rules = {};
  const startIndex = lines.findIndex(
    (line) => line.includes("标的") && line.includes("主题入场") && line.includes("确认入场")
  );
  if (startIndex === -1) {
    return rules;
  }

  for (let index = startIndex + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line || line.includes("如果你周一只做两笔")) {
      break;
    }
    const parts = line.split(/\t+/).map((part) => part.trim()).filter(Boolean);
    if (parts.length < 4) {
      continue;
    }
    const stock = sanitizeLegLabel(extractStockCandidates(parts[0])[0] || parts[0]);
    if (!stock) {
      continue;
    }
    rules[stock] = {
      themeEntry: parts[1],
      confirmEntry: parts[2],
      invalidation: parts[3]
    };
  }

  return rules;
}

function matchPlanLeg(text, patterns, fallback) {
  for (const pattern of patterns) {
    const match = String(text || "").match(pattern);
    if (!match) {
      continue;
    }
    const candidate = sanitizeLegLabel(match[1] || "");
    if (candidate) {
      return candidate;
    }
  }
  return fallback;
}

function matchConfirmLeg(text) {
  const normalizedText = String(text || "").replace(/哪一笔是确认后做的/g, "");
  const patterns = [
    /第二优先才是\s*([\p{Script=Han}A-Za-z0-9·]+)/u,
    /弹性选\s*([\p{Script=Han}A-Za-z0-9·]+)/u,
    /([\p{Script=Han}A-Za-z0-9·]+)\s*确认后(?:再)?做/u,
    /([\p{Script=Han}A-Za-z0-9·]+)\s*confirm(?:ed)?(?: then)?(?: enter| do)?/iu
  ];
  for (const pattern of patterns) {
    const match = normalizedText.match(pattern);
    if (!match) {
      continue;
    }
    const candidate = sanitizeLegLabel(match[1] || "");
    if (candidate && !/主腿|main leg|对冲|hedge/i.test(candidate)) {
      return candidate;
    }
  }
  return "";
}

function inferLegFromLines(lines, patterns, fallback) {
  for (const line of lines) {
    if (!patterns.some((pattern) => pattern.test(line))) {
      continue;
    }
    const candidates = extractStockCandidates(line);
    if (candidates.length > 0) {
      return sanitizeLegLabel(candidates[0]) || fallback;
    }
  }
  return fallback;
}

function extractStockCandidates(line) {
  return (String(line || "").match(/[\p{Script=Han}·]{2,16}/gu) || []).filter(
    (token) => !LEG_LABEL_STOPWORDS.has(token)
  );
}

function sanitizeLegLabel(value) {
  return String(value || "")
    .split(/[,+，。；;\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .pop()
    ?.replace(/主腿|弹性腿|对冲腿/g, "")
    ?.replace(/\b(run|按|with|then|enter|do)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim() || "";
}

const LEG_LABEL_STOPWORDS = new Set([
  "周一盘前执行版",
  "一句话结论",
  "主腿",
  "弹性腿",
  "对冲腿",
  "第一优先是",
  "第二优先才是",
  "对冲优先是",
  "主做",
  "弹性选",
  "如果担心消息反转",
  "就加",
  "最纯原油映射",
  "风险溢价高弹性",
  "避险表达",
  "确认入场",
  "主题入场",
  "失效",
  "哪一笔是",
  "追高",
  "盘中执行模板",
  "圆桌讨论",
  "交易复盘导师模式"
]);

const ROUNDTABLE_MENTORS = ["Druckenmiller", "Howard Marks", "Dalio"];
