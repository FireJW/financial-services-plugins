/**
 * Daily Trade Plan Validation
 *
 * Connects the existing legendary-investor decision + review pipeline
 * into a single validation loop that takes:
 *   - a plan run export (legendary-investor-last-run.json)
 *   - preopen auction facts (new: 9:15-9:25 call auction data)
 *   - intraday facts (renamed: intraday_midday)
 *   - postclose facts
 *   - optional X supplementation signals
 *
 * and produces a validation record with:
 *   - status: success | partial | fail | too_early
 *   - why_right / why_wrong
 *   - method_delta / next_rule_changes
 *   - x_supporting_signals / x_contradicting_signals
 *   - execution_feasibility (new: tradeable | degraded | untradeable)
 *
 * Contracts:
 *   - Preopen Auction Facts: { trade_day, as_of, plan_source, auction_snapshots[], fact_flags{}, execution_risk_flags{}, operator_notes }
 *   - Intraday Facts: { trade_day, as_of, plan_source, market, ticker_snapshots[], fact_flags{}, operator_notes }
 *   - Postclose Facts: { trade_day, as_of, ticker_snapshots[], fact_flags{}, execution_result, missed_or_wrong_assumptions[] }
 *   - Validation Record: { plan_id, trade_day, status, decision_verdict, review_verdict, execution_feasibility, ... }
 *
 * Supported modes: "preopen_auction", "intraday_midday" (alias: "intraday"), "postclose"
 */

import { buildLegendaryInvestorDecision } from "./legendary-investor-decision.mjs";
import { buildLegendaryInvestorReview } from "./legendary-investor-review.mjs";

// ── Freshness TTLs (ms) ────────────────────────────────────────────
const FRESHNESS_TTLS = {
  auction_snapshot: 30 * 60 * 1000,
  intraday_midday: 2 * 60 * 60 * 1000,
  postclose: 24 * 60 * 60 * 1000,
  prev_close: 24 * 60 * 60 * 1000,
  history_rows: 7 * 24 * 60 * 60 * 1000,
};

// ── Mode Aliases ───────────────────────────────────────────────────
const MODE_ALIASES = { intraday: "intraday_midday" };
const SUPPORTED_MODES = ["preopen_auction", "intraday_midday", "postclose"];

function resolveMode(raw) {
  const m = MODE_ALIASES[raw] || raw || "postclose";
  return SUPPORTED_MODES.includes(m) ? m : "postclose";
}

// ── Contract Builders ───────────────────────────────────────────────

export function buildPreopenAuctionFacts(input = {}) {
  const snapshots = Array.isArray(input.auction_snapshots) ? input.auction_snapshots : [];
  return {
    trade_day: input.trade_day || null,
    as_of: input.as_of || new Date().toISOString(),
    plan_source: input.plan_source || null,
    auction_snapshots: snapshots.map(normalizeAuctionSnapshot),
    fact_flags: input.fact_flags && typeof input.fact_flags === "object" ? input.fact_flags : {},
    execution_risk_flags: deriveExecutionRiskFlags(snapshots),
    operator_notes: input.operator_notes || "",
  };
}

function normalizeAuctionSnapshot(snap = {}) {
  const gapPct = snap.auction_gap_pct_vs_prev_close ?? computeGapPct(snap);
  return {
    ticker: snap.ticker || null,
    name: snap.name || null,
    auction_price: snap.auction_price ?? null,
    prev_close: snap.prev_close ?? null,
    auction_gap_pct_vs_prev_close: gapPct,
    indicative_turnover: snap.indicative_turnover ?? null,
    indicative_volume_ratio: snap.indicative_volume_ratio ?? null,
    auction_strength_label: classifyAuctionStrength(gapPct, snap.indicative_volume_ratio),
    auction_risk_label: classifyAuctionRisk(gapPct),
  };
}

function computeGapPct(snap) {
  if (snap.auction_price != null && snap.prev_close != null && snap.prev_close !== 0) {
    return ((snap.auction_price - snap.prev_close) / snap.prev_close) * 100;
  }
  return null;
}

function classifyAuctionStrength(gapPct, volRatio) {
  const absGap = Math.abs(gapPct ?? 0);
  const vr = volRatio ?? 1;
  if (absGap >= 5 || absGap >= 9.8) return "extreme";
  if (absGap >= 3 || vr > 2.0) return "strong";
  if (absGap >= 0.5 || vr >= 0.8) return "moderate";
  return "weak";
}

function classifyAuctionRisk(gapPct) {
  const absGap = Math.abs(gapPct ?? 0);
  if (absGap >= 5) return "extreme_gap";
  if (absGap >= 3) return "gap_risk";
  return "normal";
}

function deriveExecutionRiskFlags(snapshots) {
  const flags = {
    any_extreme_gap: false,
    primary_leg_gap_risk: false,
    all_legs_untradeable: false,
  };
  if (!Array.isArray(snapshots) || snapshots.length === 0) return flags;

  let untradeableCount = 0;
  for (let i = 0; i < snapshots.length; i++) {
    const absGap = Math.abs(snapshots[i].auction_gap_pct_vs_prev_close ?? 0);
    if (absGap >= 5) {
      flags.any_extreme_gap = true;
      untradeableCount++;
    }
    if (i === 0 && absGap >= 3) {
      flags.primary_leg_gap_risk = true;
    }
  }
  if (untradeableCount === snapshots.length && snapshots.length > 0) {
    flags.all_legs_untradeable = true;
  }
  return flags;
}

export function buildIntradayFacts(input = {}) {
  return {
    trade_day: input.trade_day || null,
    as_of: input.as_of || new Date().toISOString(),
    plan_source: input.plan_source || null,
    market: input.market || "A-share",
    ticker_snapshots: Array.isArray(input.ticker_snapshots) ? input.ticker_snapshots : [],
    fact_flags: input.fact_flags && typeof input.fact_flags === "object" ? input.fact_flags : {},
    operator_notes: input.operator_notes || ""
  };
}

// Alias for backward compatibility
export const buildIntradayMiddayFacts = buildIntradayFacts;

export function buildPostcloseFacts(input = {}) {
  return {
    trade_day: input.trade_day || null,
    as_of: input.as_of || new Date().toISOString(),
    ticker_snapshots: Array.isArray(input.ticker_snapshots) ? input.ticker_snapshots : [],
    fact_flags: input.fact_flags && typeof input.fact_flags === "object" ? input.fact_flags : {},
    execution_result: input.execution_result || null,
    missed_or_wrong_assumptions: Array.isArray(input.missed_or_wrong_assumptions)
      ? input.missed_or_wrong_assumptions
      : []
  };
}

export function buildValidationRecord(input = {}) {
  return {
    plan_id: input.plan_id || null,
    trade_day: input.trade_day || null,
    generated_at: input.generated_at || new Date().toISOString(),
    status: input.status || "too_early",
    decision_verdict: input.decision_verdict || null,
    review_verdict: input.review_verdict || null,
    execution_feasibility: input.execution_feasibility || null,
    x_supporting_signals: Array.isArray(input.x_supporting_signals) ? input.x_supporting_signals : [],
    x_contradicting_signals: Array.isArray(input.x_contradicting_signals) ? input.x_contradicting_signals : [],
    why_right: Array.isArray(input.why_right) ? input.why_right : [],
    why_wrong: Array.isArray(input.why_wrong) ? input.why_wrong : [],
    method_delta: Array.isArray(input.method_delta) ? input.method_delta : [],
    next_rule_changes: Array.isArray(input.next_rule_changes) ? input.next_rule_changes : [],
    fact_layer_issues: Array.isArray(input.fact_layer_issues) ? input.fact_layer_issues : [],
    timing_issues: Array.isArray(input.timing_issues) ? input.timing_issues : [],
    x_explanation: input.x_explanation || "",
    preopen_auction_facts: input.preopen_auction_facts || null,
    intraday_facts: input.intraday_facts || null,
    postclose_facts: input.postclose_facts || null
  };
}

// ── Validation Logic ────────────────────────────────────────────────

/**
 * Run daily validation.
 *
 * @param {object} exportData - The legendary-investor-last-run.json content
 * @param {object} options
 * @param {object} options.preopenAuctionFacts - Raw preopen auction facts (will be normalized)
 * @param {object} options.intradayFacts - Raw intraday/midday facts (will be normalized)
 * @param {object} options.postcloseFacts - Raw postclose facts (will be normalized)
 * @param {object[]} options.xSignals - Optional X supplementation signals
 * @param {string} options.mode - "preopen_auction", "intraday_midday" (alias: "intraday"), or "postclose"
 * @returns {object} Validation record
 */
export function runDailyValidation(exportData, options = {}) {
  const mode = resolveMode(options.mode);
  const preopen = options.preopenAuctionFacts
    ? buildPreopenAuctionFacts(options.preopenAuctionFacts)
    : null;
  const intraday = options.intradayFacts ? buildIntradayFacts(options.intradayFacts) : null;
  const postclose = options.postcloseFacts ? buildPostcloseFacts(options.postcloseFacts) : null;
  const xSignals = Array.isArray(options.xSignals) ? options.xSignals : [];

  // Derive decision facts from all available stage data
  const decisionFacts = deriveDecisionFacts(exportData, intraday, postclose, mode);
  const decisionReport = buildLegendaryInvestorDecision(exportData, decisionFacts);

  // Derive review facts from postclose (only meaningful in postclose mode)
  const reviewFacts = mode === "postclose" ? deriveReviewFacts(exportData, postclose) : {};
  const reviewReport = mode === "postclose"
    ? buildLegendaryInvestorReview(exportData, reviewFacts)
    : null;

  // Build execution feasibility from preopen auction data
  const executionFeasibility = buildExecutionFeasibilityFromAuction(preopen, decisionReport);

  // Classify X signals
  const xSupporting = xSignals.filter((s) => s.direction === "supporting");
  const xContradicting = xSignals.filter((s) => s.direction === "contradicting");

  // Determine overall status
  const status = determineValidationStatus(decisionReport, reviewReport, mode, intraday, postclose, preopen);

  // Build explanation layers
  const whyRight = buildWhyRight(decisionReport, reviewReport, mode);
  const whyWrong = buildWhyWrong(decisionReport, reviewReport, mode);
  const factLayerIssues = buildFactLayerIssues(decisionReport, intraday, postclose, preopen);
  const timingIssues = buildTimingIssues(decisionReport, reviewReport, postclose);
  const methodDelta = buildMethodDelta(reviewReport, whyWrong, factLayerIssues, timingIssues);
  const nextRuleChanges = buildNextRuleChanges(reviewReport, methodDelta);
  const xExplanation = buildXExplanation(xSupporting, xContradicting);

  // Derive plan_id from export
  const planId = derivePlanId(exportData);
  const tradeDay = preopen?.trade_day || intraday?.trade_day || postclose?.trade_day || null;

  return buildValidationRecord({
    plan_id: planId,
    trade_day: tradeDay,
    generated_at: new Date().toISOString(),
    status,
    decision_verdict: decisionReport.verdict,
    review_verdict: reviewReport?.verdict || null,
    execution_feasibility: executionFeasibility,
    x_supporting_signals: xSupporting.map(formatXSignal),
    x_contradicting_signals: xContradicting.map(formatXSignal),
    why_right: whyRight,
    why_wrong: whyWrong,
    method_delta: methodDelta,
    next_rule_changes: nextRuleChanges,
    fact_layer_issues: factLayerIssues,
    timing_issues: timingIssues,
    x_explanation: xExplanation,
    preopen_auction_facts: preopen,
    intraday_facts: intraday,
    postclose_facts: postclose
  });
}

/**
 * Render a validation record as human-readable markdown.
 */
export function renderValidationRecord(record, options = {}) {
  const lines = [
    "# Daily Trade Plan Validation",
    "",
    `Plan: ${record.plan_id || "(unknown)"}`,
    `Trade Day: ${record.trade_day || "(unknown)"}`,
    `Generated: ${record.generated_at}`,
    `Status: **${record.status}**`,
    `Decision Verdict: ${record.decision_verdict || "(none)"}`,
    `Review Verdict: ${record.review_verdict || "(none)"}`,
    ""
  ];

  // Execution feasibility section
  if (record.execution_feasibility) {
    const ef = record.execution_feasibility;
    lines.push(`Execution Feasibility: **${ef.feasibility_verdict}**${ef.modulation?.verdict_suffix ? ` → ${record.decision_verdict}_${ef.modulation.verdict_suffix}` : ""}`);
    const activeFlags = Object.entries(ef.flags || {}).filter(([, v]) => v);
    if (activeFlags.length > 0) {
      lines.push("");
      lines.push("### Execution Risk Flags");
      for (const [key] of activeFlags) {
        lines.push(`- ${key}`);
      }
    }
    lines.push("");
  }

  if (record.why_right.length > 0) {
    lines.push("## Why Right");
    for (const item of record.why_right) {
      lines.push(`- ${item}`);
    }
    lines.push("");
  }

  if (record.why_wrong.length > 0) {
    lines.push("## Why Wrong");
    for (const item of record.why_wrong) {
      lines.push(`- ${item}`);
    }
    lines.push("");
  }

  if (record.fact_layer_issues.length > 0) {
    lines.push("## Fact Layer Issues");
    for (const item of record.fact_layer_issues) {
      lines.push(`- ${item}`);
    }
    lines.push("");
  }

  if (record.timing_issues.length > 0) {
    lines.push("## Timing / Confirmation / Execution Issues");
    for (const item of record.timing_issues) {
      lines.push(`- ${item}`);
    }
    lines.push("");
  }

  if (record.x_supporting_signals.length > 0 || record.x_contradicting_signals.length > 0) {
    lines.push("## X Supplementation");
    if (record.x_supporting_signals.length > 0) {
      lines.push("### Supporting");
      for (const sig of record.x_supporting_signals) {
        lines.push(`- ${sig}`);
      }
    }
    if (record.x_contradicting_signals.length > 0) {
      lines.push("### Contradicting");
      for (const sig of record.x_contradicting_signals) {
        lines.push(`- ${sig}`);
      }
    }
    if (record.x_explanation) {
      lines.push("");
      lines.push(`X Explanation: ${record.x_explanation}`);
    }
    lines.push("");
  }

  if (record.method_delta.length > 0) {
    lines.push("## Method Delta");
    for (const item of record.method_delta) {
      lines.push(`- ${item}`);
    }
    lines.push("");
  }

  if (record.next_rule_changes.length > 0) {
    lines.push("## Next Rule Changes");
    for (const item of record.next_rule_changes) {
      lines.push(`- ${item}`);
    }
    lines.push("");
  }

  return lines.join("\n").trim();
}

// ── Execution Feasibility ──────────────────────────────────────────

function buildExecutionFeasibilityFromAuction(preopen, decisionReport) {
  const flags = {
    thesis_right_but_untradeable_open: false,
    gap_risk_too_high: false,
    high_open_low_rr: false,
    auction_not_confirmed: false,
    strong_close_but_unchaseable: false,
    end_stage_acceleration: false,
    high_consensus_low_rr_chase: false,
    primary_leg_no_tradeable_zone: false,
    confirm_leg_already_consensus: false,
  };

  if (!preopen) {
    return { feasibility_verdict: "degraded", flags, modulation: { verdict_suffix: null }, data_quality: "auction_data_missing" };
  }

  const riskFlags = preopen.execution_risk_flags || {};

  if (riskFlags.any_extreme_gap) flags.gap_risk_too_high = true;
  if (riskFlags.primary_leg_gap_risk) flags.primary_leg_no_tradeable_zone = true;
  if (riskFlags.all_legs_untradeable) flags.thesis_right_but_untradeable_open = true;

  // Check individual snapshots for high-open-low-rr pattern
  for (const snap of preopen.auction_snapshots || []) {
    const absGap = Math.abs(snap.auction_gap_pct_vs_prev_close ?? 0);
    if (absGap >= 3 && (snap.indicative_volume_ratio ?? 1) < 1.0) {
      flags.high_open_low_rr = true;
    }
    if (snap.auction_strength_label === "weak" || snap.auction_risk_label === "extreme_gap") {
      flags.auction_not_confirmed = true;
    }
  }

  // Determine verdict
  const activeCount = Object.values(flags).filter(Boolean).length;
  let feasibility_verdict = "tradeable";
  let verdict_suffix = null;

  if (flags.thesis_right_but_untradeable_open || flags.gap_risk_too_high) {
    feasibility_verdict = "untradeable";
    verdict_suffix = "BUT_WAIT";
  } else if (activeCount > 0) {
    feasibility_verdict = "degraded";
    verdict_suffix = "CAUTIOUS";
  }

  return {
    feasibility_verdict,
    flags,
    modulation: { verdict_suffix },
  };
}

// ── Internal Helpers ────────────────────────────────────────────────

function deriveDecisionFacts(exportData, intraday, postclose, mode) {
  const payload = exportData && typeof exportData === "object" ? exportData : {};
  const playbookKey = payload.playbook?.key || "event_driven_risk";
  const facts = {};

  // Merge fact_flags from intraday and postclose into decision-compatible keys
  const flags = {
    ...(intraday?.fact_flags || {}),
    ...(postclose?.fact_flags || {})
  };

  switch (playbookKey) {
    case "event_driven_risk":
      if (flags.no_agreement !== undefined) facts.no_agreement = flags.no_agreement;
      if (flags.substantive_progress !== undefined) facts.substantive_progress = flags.substantive_progress;
      if (flags.risk_unresolved !== undefined) facts.risk_unresolved = flags.risk_unresolved;
      if (flags.primary_leg_confirmed !== undefined) facts.primary_leg_confirmed = flags.primary_leg_confirmed;
      if (flags.hedge_leg_confirmed !== undefined) facts.hedge_leg_confirmed = flags.hedge_leg_confirmed;
      if (flags.confirm_leg_confirmed !== undefined) facts.confirm_leg_confirmed = flags.confirm_leg_confirmed;
      break;
    case "supply_demand_cycle":
      if (flags.price_hike_confirmed !== undefined) facts.price_hike_confirmed = flags.price_hike_confirmed;
      if (flags.supply_shortage_confirmed !== undefined) facts.supply_shortage_confirmed = flags.supply_shortage_confirmed;
      if (flags.high_utilization_confirmed !== undefined) facts.high_utilization_confirmed = flags.high_utilization_confirmed;
      if (flags.primary_leg_confirmed !== undefined) facts.primary_leg_confirmed = flags.primary_leg_confirmed;
      if (flags.hedge_leg_confirmed !== undefined) facts.hedge_leg_confirmed = flags.hedge_leg_confirmed;
      if (flags.confirm_leg_confirmed !== undefined) facts.confirm_leg_confirmed = flags.confirm_leg_confirmed;
      break;
    case "valuation_quality":
      if (flags.quality_ok !== undefined) facts.quality_ok = flags.quality_ok;
      if (flags.capital_allocation_ok !== undefined) facts.capital_allocation_ok = flags.capital_allocation_ok;
      if (flags.cashflow_ok !== undefined) facts.cashflow_ok = flags.cashflow_ok;
      if (flags.odds_ok !== undefined) facts.odds_ok = flags.odds_ok;
      if (flags.hold_without_story !== undefined) facts.hold_without_story = flags.hold_without_story;
      break;
    case "macro_reflexive":
      if (flags.liquidity_ok !== undefined) facts.liquidity_ok = flags.liquidity_ok;
      if (flags.cross_asset_confirmed !== undefined) facts.cross_asset_confirmed = flags.cross_asset_confirmed;
      if (flags.macro_alignment_ok !== undefined) facts.macro_alignment_ok = flags.macro_alignment_ok;
      if (flags.confirm_leg_confirmed !== undefined) facts.confirm_leg_confirmed = flags.confirm_leg_confirmed;
      break;
    default:
      // Pass through all flags
      Object.assign(facts, flags);
      break;
  }

  return facts;
}

function deriveReviewFacts(exportData, postclose) {
  const payload = exportData && typeof exportData === "object" ? exportData : {};
  const playbookKey = payload.playbook?.key || "event_driven_risk";
  const flags = postclose?.fact_flags || {};
  const facts = {};

  switch (playbookKey) {
    case "event_driven_risk":
      if (flags.traded_fact_not_story !== undefined) facts.traded_fact_not_story = flags.traded_fact_not_story;
      if (flags.primary_leg_was_stable !== undefined) facts.primary_leg_was_stable = flags.primary_leg_was_stable;
      if (flags.hedge_leg_worked !== undefined) facts.hedge_leg_worked = flags.hedge_leg_worked;
      if (flags.confirm_leg_was_confirmed !== undefined) facts.confirm_leg_was_confirmed = flags.confirm_leg_was_confirmed;
      if (flags.chased_confirm_leg !== undefined) facts.chased_confirm_leg = flags.chased_confirm_leg;
      if (flags.respected_invalidation !== undefined) facts.respected_invalidation = flags.respected_invalidation;
      break;
    case "supply_demand_cycle":
      if (flags.traded_supply_demand_fact !== undefined) facts.traded_supply_demand_fact = flags.traded_supply_demand_fact;
      if (flags.primary_leg_had_pricing_power !== undefined) facts.primary_leg_had_pricing_power = flags.primary_leg_had_pricing_power;
      if (flags.hedge_leg_worked !== undefined) facts.hedge_leg_worked = flags.hedge_leg_worked;
      if (flags.confirm_leg_was_confirmed !== undefined) facts.confirm_leg_was_confirmed = flags.confirm_leg_was_confirmed;
      if (flags.chased_confirm_leg !== undefined) facts.chased_confirm_leg = flags.chased_confirm_leg;
      if (flags.respected_invalidation !== undefined) facts.respected_invalidation = flags.respected_invalidation;
      break;
    case "valuation_quality":
      if (flags.quality_thesis_intact !== undefined) facts.quality_thesis_intact = flags.quality_thesis_intact;
      if (flags.odds_were_acceptable !== undefined) facts.odds_were_acceptable = flags.odds_were_acceptable;
      if (flags.hold_without_story !== undefined) facts.hold_without_story = flags.hold_without_story;
      if (flags.chased_price !== undefined) facts.chased_price = flags.chased_price;
      if (flags.added_without_new_evidence !== undefined) facts.added_without_new_evidence = flags.added_without_new_evidence;
      if (flags.respected_price_discipline !== undefined) facts.respected_price_discipline = flags.respected_price_discipline;
      break;
    case "macro_reflexive":
      if (flags.chain_confirmed !== undefined) facts.chain_confirmed = flags.chain_confirmed;
      if (flags.cross_asset_aligned !== undefined) facts.cross_asset_aligned = flags.cross_asset_aligned;
      if (flags.variables_diverged !== undefined) facts.variables_diverged = flags.variables_diverged;
      if (flags.added_without_confirmation !== undefined) facts.added_without_confirmation = flags.added_without_confirmation;
      if (flags.respected_risk_budget !== undefined) facts.respected_risk_budget = flags.respected_risk_budget;
      break;
    default:
      Object.assign(facts, flags);
      break;
  }

  return facts;
}

function determineValidationStatus(decisionReport, reviewReport, mode, intraday, postclose, preopen) {
  // Preopen auction only — always too early
  if (mode === "preopen_auction") {
    return "too_early";
  }

  // Intraday midday mode (alias: intraday) — no postclose data yet
  if (mode === "intraday_midday" && !postclose) {
    if (decisionReport.verdict === "GO") return "partial";
    if (decisionReport.verdict === "WATCH") return "too_early";
    if (decisionReport.verdict === "REDUCE") return "partial";
    return "too_early";
  }

  // Postclose mode: combine decision + review
  if (!reviewReport) return "too_early";

  const dv = decisionReport.verdict;
  const rv = reviewReport.verdict;

  // Both clean
  if (dv === "GO" && rv === "CLEAN") return "success";

  // Decision was right but execution had issues
  if (dv === "GO" && rv === "MIXED") return "partial";
  if (dv === "GO" && rv === "FAIL") return "fail";

  // Decision said watch/reduce, review says clean (dodged a bullet or plan was conservative)
  if ((dv === "WATCH" || dv === "REDUCE") && rv === "CLEAN") return "partial";

  // Both negative
  if ((dv === "WATCH" || dv === "REDUCE") && rv === "FAIL") return "fail";

  // Mixed
  return "partial";
}

function buildWhyRight(decisionReport, reviewReport, mode) {
  const items = [];

  if (decisionReport.rationale?.length > 0) {
    for (const r of decisionReport.rationale) {
      if (!r.includes("缺失") && !r.includes("missing")) {
        items.push(`[Decision] ${r}`);
      }
    }
  }

  if (reviewReport?.strengths?.length > 0) {
    for (const s of reviewReport.strengths) {
      items.push(`[Review] ${s}`);
    }
  }

  return items;
}

function buildWhyWrong(decisionReport, reviewReport, mode) {
  const items = [];

  if (decisionReport.missingFacts?.length > 0) {
    for (const f of decisionReport.missingFacts) {
      items.push(`[Decision missing fact] ${f}`);
    }
  }

  if (reviewReport?.failures?.length > 0) {
    for (const f of reviewReport.failures) {
      items.push(`[Review] ${f}`);
    }
  }

  return items;
}

function buildFactLayerIssues(decisionReport, intraday, postclose, preopen) {
  const issues = [];

  // Check for missing facts in decision
  if (decisionReport.missingFacts?.length > 0) {
    issues.push(`Decision had ${decisionReport.missingFacts.length} missing fact(s): ${decisionReport.missingFacts.join(", ")}`);
  }

  // Check for missed assumptions in postclose
  if (postclose?.missed_or_wrong_assumptions?.length > 0) {
    for (const assumption of postclose.missed_or_wrong_assumptions) {
      issues.push(`Wrong assumption: ${assumption}`);
    }
  }

  // Check for fact board items that were "no"
  const noFacts = (decisionReport.factBoard || []).filter((f) => f.status === "no");
  for (const fact of noFacts) {
    issues.push(`Fact failed: ${fact.label}`);
  }

  // Per-stage freshness checks with TTLs
  const tradeDay = preopen?.trade_day || intraday?.trade_day || postclose?.trade_day;
  if (tradeDay) {
    const tradeDayMs = new Date(tradeDay).getTime();
    if (!Number.isNaN(tradeDayMs)) {
      const stageChecks = [
        ["preopen_auction", preopen, FRESHNESS_TTLS.auction_snapshot],
        ["intraday_midday", intraday, FRESHNESS_TTLS.intraday_midday],
        ["postclose", postclose, FRESHNESS_TTLS.postclose],
      ];
      for (const [label, facts, ttl] of stageChecks) {
        if (!facts) continue;
        const asOf = facts.as_of;
        if (!asOf) {
          issues.push(`stale_${label}_facts: as_of is missing`);
          continue;
        }
        const asOfMs = new Date(asOf).getTime();
        if (Number.isNaN(asOfMs)) {
          issues.push(`stale_${label}_facts: as_of is invalid`);
          continue;
        }
        const deltaMs = Math.abs(tradeDayMs - asOfMs);
        if (deltaMs > ttl) {
          const deltaHours = Math.round(deltaMs / (1000 * 60 * 60));
          issues.push(`stale_${label}_facts: as_of is ${deltaHours}h old (TTL: ${Math.round(ttl / (1000 * 60 * 60))}h)`);
        }
      }
    }
  }

  return issues;
}

function buildTimingIssues(decisionReport, reviewReport, postclose) {
  const issues = [];

  if (reviewReport?.failures?.length > 0) {
    for (const f of reviewReport.failures) {
      if (/确认|追高|提前|纪律|失效/.test(f)) {
        issues.push(f);
      }
    }
  }

  if (postclose?.execution_result && /追高|提前|错过/.test(postclose.execution_result)) {
    issues.push(`Execution: ${postclose.execution_result}`);
  }

  return issues;
}

function buildMethodDelta(reviewReport, whyWrong, factLayerIssues, timingIssues) {
  const deltas = [];

  // From review nextTime
  if (reviewReport?.nextTime?.length > 0) {
    for (const item of reviewReport.nextTime) {
      deltas.push(item);
    }
  }

  // From fact layer issues — derive method changes
  if (factLayerIssues.length > 0) {
    deltas.push(`Fact layer had ${factLayerIssues.length} issue(s) — review fact-checking rigor before next plan.`);
  }

  // From timing issues
  if (timingIssues.length > 0) {
    deltas.push(`Timing/execution had ${timingIssues.length} issue(s) — review confirmation discipline.`);
  }

  return deltas;
}

function buildNextRuleChanges(reviewReport, methodDelta) {
  const rules = [];

  // Extract if-then style rules from review nextTime
  if (reviewReport?.nextTime?.length > 0) {
    for (const item of reviewReport.nextTime) {
      if (/只有在|不加|先缩|先减|不追/.test(item)) {
        rules.push(item);
      }
    }
  }

  // If method delta suggests fact-checking issues, add a rule
  for (const delta of methodDelta) {
    if (/fact layer|fact-checking/.test(delta)) {
      rules.push("Before next plan: verify all critical facts are filled before execution.");
    }
    if (/confirmation discipline/.test(delta)) {
      rules.push("Before next plan: write confirmation conditions before market open, not after.");
    }
  }

  // Deduplicate
  return [...new Set(rules)];
}

function buildXExplanation(supporting, contradicting) {
  if (supporting.length === 0 && contradicting.length === 0) {
    return "";
  }

  const parts = [];
  if (supporting.length > 0) {
    parts.push(`${supporting.length} supporting X signal(s)`);
  }
  if (contradicting.length > 0) {
    parts.push(`${contradicting.length} contradicting X signal(s)`);
  }
  return parts.join("; ");
}

function formatXSignal(signal) {
  if (typeof signal === "string") return signal;
  const handle = signal.handle || signal.author || "";
  const content = signal.content || signal.text || signal.summary || "";
  const asOf = signal.as_of || "";
  return `${handle ? `@${handle}: ` : ""}${content}${asOf ? ` (as_of: ${asOf})` : ""}`;
}

function derivePlanId(exportData) {
  if (!exportData || typeof exportData !== "object") return null;
  if (exportData.planInput) {
    const firstLine = String(exportData.planInput).split(/\r?\n/).map((l) => l.trim()).find(Boolean) || "";
    return firstLine.replace(/^#+\s*/, "").slice(0, 64).trim() || null;
  }
  if (exportData.summary?.scenarioLabel) {
    return exportData.summary.scenarioLabel;
  }
  return null;
}
