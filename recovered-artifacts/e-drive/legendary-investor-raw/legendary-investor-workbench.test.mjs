import test from "node:test";
import assert from "node:assert/strict";

import {
  parseLegendaryWorkbenchArgs
} from "../scripts/legendary-investor-workbench.mjs";

import {
  analyzeTradingPlan
} from "../src/legendary-investor-reasoner.mjs";

// ── --fresh-session flag ────────────────────────────────────────────────

test("parseLegendaryWorkbenchArgs recognizes --fresh-session flag", () => {
  const args = ["--plan-text", "test plan", "--execute", "--fresh-session"];
  const parsed = parseLegendaryWorkbenchArgs(args);
  assert.equal(parsed.freshSession, true);
});

test("parseLegendaryWorkbenchArgs defaults freshSession to false", () => {
  const args = ["--plan-text", "test plan", "--execute"];
  const parsed = parseLegendaryWorkbenchArgs(args);
  assert.equal(parsed.freshSession, false);
});

// ── --playbook override ─────────────────────────────────────────────────

test("parseLegendaryWorkbenchArgs recognizes --playbook flag", () => {
  const args = ["--plan-text", "test plan", "--execute", "--playbook", "supply_demand_cycle"];
  const parsed = parseLegendaryWorkbenchArgs(args);
  assert.equal(parsed.playbookOverride, "supply_demand_cycle");
});

test("parseLegendaryWorkbenchArgs rejects invalid --playbook value", () => {
  const args = ["--plan-text", "test plan", "--execute", "--playbook", "invalid_playbook"];
  assert.throws(
    () => parseLegendaryWorkbenchArgs(args),
    (err) => err.code === "USAGE" || /must be one of/.test(err.message)
  );
});

test("analyzeTradingPlan uses playbookOverride when provided", () => {
  const planText = "涨价主题 电子布 主腿中材科技 对冲腿中国巨石 弹性腿宏和科技";
  const result = analyzeTradingPlan(planText, { playbookOverride: "valuation_quality" });
  assert.equal(result.roundtablePlaybookKey, "valuation_quality");
});

test("analyzeTradingPlan auto-detects playbook when no override", () => {
  const planText = "涨价主题 电子布 供不应求 主腿中材科技 对冲腿中国巨石 弹性腿宏和科技";
  const result = analyzeTradingPlan(planText);
  assert.equal(result.roundtablePlaybookKey, "supply_demand_cycle");
});
