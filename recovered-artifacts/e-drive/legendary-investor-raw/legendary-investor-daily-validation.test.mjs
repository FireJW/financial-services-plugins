import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPreopenAuctionFacts,
  buildIntradayFacts,
  buildIntradayMiddayFacts,
  buildPostcloseFacts,
  buildValidationRecord,
  runDailyValidation,
  renderValidationRecord,
} from "../src/legendary-investor-daily-validation.mjs";

import {
  buildExecutionFeasibility,
} from "../src/legendary-investor-decision.mjs";

// ── Stub export data ──────────────────────────────────────────────────
const STUB_EXPORT = {
  playbook: { key: "event_driven_risk", label: "事件驱动风险委员会" },
  summary: {
    scenarioLabel: "test scenario",
    primaryLeg: "主腿A",
    hedgeLeg: "对冲腿B",
    confirmLeg: "弹性腿C",
  },
  committee: {
    verdict: { defaultStructure: "default-struct", downgradeSequence: "降级" },
    backupPlan: "backup",
    primaryPlan: "primary-plan",
  },
};

// ── buildPreopenAuctionFacts ──────────────────────────────────────────

test("buildPreopenAuctionFacts normalizes auction snapshots", () => {
  const facts = buildPreopenAuctionFacts({
    trade_day: "2026-04-14",
    auction_snapshots: [
      { ticker: "000001.SZ", auction_price: 10.5, prev_close: 10.0 },
    ],
  });
  assert.equal(facts.trade_day, "2026-04-14");
  assert.equal(facts.auction_snapshots.length, 1);
  const snap = facts.auction_snapshots[0];
  assert.equal(snap.ticker, "000001.SZ");
  assert.ok(typeof snap.auction_gap_pct_vs_prev_close === "number");
  assert.ok(snap.auction_strength_label);
  assert.ok(snap.auction_risk_label);
});

test("buildPreopenAuctionFacts computes gap pct from price/prev_close", () => {
  const facts = buildPreopenAuctionFacts({
    auction_snapshots: [
      { ticker: "T1", auction_price: 11.0, prev_close: 10.0 },
    ],
  });
  assert.ok(Math.abs(facts.auction_snapshots[0].auction_gap_pct_vs_prev_close - 10.0) < 0.01);
});

test("buildPreopenAuctionFacts derives execution_risk_flags for extreme gap", () => {
  const facts = buildPreopenAuctionFacts({
    auction_snapshots: [
      { ticker: "T1", auction_gap_pct_vs_prev_close: 6.0 },
    ],
  });
  assert.equal(facts.execution_risk_flags.any_extreme_gap, true);
});

test("buildPreopenAuctionFacts returns empty flags for no snapshots", () => {
  const facts = buildPreopenAuctionFacts({});
  assert.equal(facts.auction_snapshots.length, 0);
  assert.equal(facts.execution_risk_flags.any_extreme_gap, false);
  assert.equal(facts.execution_risk_flags.all_legs_untradeable, false);
});

// ── Backward compatibility: intraday alias ────────────────────────────

test("buildIntradayMiddayFacts is an alias for buildIntradayFacts", () => {
  assert.strictEqual(buildIntradayMiddayFacts, buildIntradayFacts);
});

test("buildIntradayFacts normalizes input", () => {
  const facts = buildIntradayFacts({ trade_day: "2026-04-14", fact_flags: { a: true } });
  assert.equal(facts.trade_day, "2026-04-14");
  assert.equal(facts.market, "A-share");
  assert.deepEqual(facts.fact_flags, { a: true });
});

// ── buildPostcloseFacts ───────────────────────────────────────────────

test("buildPostcloseFacts normalizes input", () => {
  const facts = buildPostcloseFacts({
    trade_day: "2026-04-14",
    execution_result: "executed",
    missed_or_wrong_assumptions: ["missed X"],
  });
  assert.equal(facts.execution_result, "executed");
  assert.deepEqual(facts.missed_or_wrong_assumptions, ["missed X"]);
});

// ── buildValidationRecord ─────────────────────────────────────────────

test("buildValidationRecord includes execution_feasibility field", () => {
  const record = buildValidationRecord({
    plan_id: "test",
    execution_feasibility: { feasibility_verdict: "tradeable", flags: {} },
  });
  assert.equal(record.execution_feasibility.feasibility_verdict, "tradeable");
});

test("buildValidationRecord includes preopen_auction_facts field", () => {
  const preopen = { trade_day: "2026-04-14", auction_snapshots: [] };
  const record = buildValidationRecord({ preopen_auction_facts: preopen });
  assert.deepEqual(record.preopen_auction_facts, preopen);
});

// ── runDailyValidation 3-stage modes ──────────────────────────────────

test("runDailyValidation preopen_auction mode returns too_early status", () => {
  const record = runDailyValidation(STUB_EXPORT, {
    mode: "preopen_auction",
    preopenAuctionFacts: {
      trade_day: "2026-04-14",
      auction_snapshots: [
        { ticker: "T1", auction_price: 10.2, prev_close: 10.0 },
      ],
    },
  });
  assert.equal(record.status, "too_early");
  assert.ok(record.execution_feasibility);
  assert.ok(record.preopen_auction_facts);
});

test("runDailyValidation intraday alias resolves to intraday_midday", () => {
  const record = runDailyValidation(STUB_EXPORT, {
    mode: "intraday",
    intradayFacts: { trade_day: "2026-04-14", fact_flags: {} },
  });
  assert.ok(["too_early", "partial"].includes(record.status));
});

test("runDailyValidation postclose mode with GO facts returns success", () => {
  const record = runDailyValidation(STUB_EXPORT, {
    mode: "postclose",
    postcloseFacts: {
      trade_day: "2026-04-14",
      fact_flags: {
        no_agreement: true,
        risk_unresolved: true,
        primary_leg_confirmed: true,
        confirm_leg_confirmed: true,
      },
      execution_result: "executed_default",
    },
  });
  assert.equal(record.decision_verdict, "GO");
  assert.ok(["success", "partial"].includes(record.status));
});

// ── buildExecutionFeasibility (from decision.mjs) ─────────────────────

test("buildExecutionFeasibility returns tradeable when no flags", () => {
  const result = buildExecutionFeasibility(null, {});
  assert.equal(result.feasibility_verdict, "tradeable");
});

test("buildExecutionFeasibility detects extreme gap as untradeable", () => {
  const auctionFacts = {
    execution_risk_flags: { any_extreme_gap: true },
    auction_snapshots: [
      { auction_gap_pct_vs_prev_close: 7, indicative_volume_ratio: 0.5 },
    ],
  };
  const result = buildExecutionFeasibility(auctionFacts, {});
  assert.equal(result.feasibility_verdict, "untradeable");
  assert.equal(result.flags.gap_risk_too_high, true);
});

test("buildExecutionFeasibility detects execution metric signals", () => {
  const result = buildExecutionFeasibility(null, {
    wyckoff_flags: { strong_close_unchaseable: { triggered: true } },
    momentum_flags: { end_stage_acceleration: { triggered: true } },
  });
  assert.equal(result.flags.strong_close_but_unchaseable, true);
  assert.equal(result.flags.end_stage_acceleration, true);
  assert.equal(result.feasibility_verdict, "degraded");
});

test("buildExecutionFeasibility returns tradeable with clean auction", () => {
  const auctionFacts = {
    execution_risk_flags: {},
    auction_snapshots: [
      { auction_gap_pct_vs_prev_close: 0.5, indicative_volume_ratio: 1.2, auction_strength_label: "moderate", auction_risk_label: "normal" },
    ],
  };
  const result = buildExecutionFeasibility(auctionFacts, {});
  assert.equal(result.feasibility_verdict, "tradeable");
});

// ── renderValidationRecord ────────────────────────────────────────────

test("renderValidationRecord includes execution feasibility section", () => {
  const record = buildValidationRecord({
    plan_id: "test",
    status: "too_early",
    execution_feasibility: {
      feasibility_verdict: "degraded",
      flags: { gap_risk_too_high: false, auction_not_confirmed: true },
      modulation: { verdict_suffix: "CAUTIOUS" },
    },
    decision_verdict: "WATCH",
  });
  const rendered = renderValidationRecord(record);
  assert.ok(rendered.includes("Execution Feasibility"));
  assert.ok(rendered.includes("degraded"));
});
