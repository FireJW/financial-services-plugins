import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildSessionStatePayload } from "../../scripts/runtime/orchestration-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const scriptPath = path.join(repoRoot, "scripts", "runtime", "build-session-state.mjs");

test("session state builder emits the fixed NOW structure with token budgets", () => {
  const inputPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-state",
    "sample-session-input.json",
  );
  const result = spawnSync("node", [scriptPath, "--input", inputPath], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);

  const output = result.stdout;
  const goalIndex = output.indexOf("## Goal");
  const currentStateIndex = output.indexOf("## Current State");
  const confirmedIndex = output.indexOf("## Confirmed Facts");
  const unresolvedIndex = output.indexOf("## Unresolved Questions");
  const nextStepIndex = output.indexOf("## Next Step");
  const risksIndex = output.indexOf("## Risks / Invalidation");

  assert.ok(goalIndex !== -1, output);
  assert.ok(goalIndex < currentStateIndex, output);
  assert.ok(currentStateIndex < confirmedIndex, output);
  assert.ok(confirmedIndex < unresolvedIndex, output);
  assert.ok(unresolvedIndex < nextStepIndex, output);
  assert.ok(nextStepIndex < risksIndex, output);
  assert.match(output, /token-budget: 120/);
  assert.match(output, /token-budget: 180/);
});

test("session state builder truncates oversized sections without dropping them", () => {
  const longFact = "Confirmed runtime detail ".repeat(120);
  const payload = buildSessionStatePayload({
    goal: "Deploy the runtime hardening layer.",
    currentState: longFact,
    confirmedFacts: [longFact, longFact],
    unresolvedQuestions: [longFact],
    nextStep: longFact,
    risks: [longFact],
  });

  assert.equal(payload.validation.ok, true, JSON.stringify(payload.validation, null, 2));
  assert.match(payload.markdown, /Current State/);
  assert.match(payload.markdown, /Confirmed Facts/);
  assert.match(payload.markdown, /\[truncated\]|Truncated for budget/);
});

test("session state builder keeps multilingual content readable", () => {
  const payload = buildSessionStatePayload({
    goal: "把 Jenny feedback workflow 转成可执行流程。",
    currentState: [
      "Worker/verifier wrapper 已经可用。",
      "Structured verifier 已经接入。",
    ],
    confirmedFacts: [
      "中文和 English mixed requests 都需要保留 hard constraints。",
    ],
    unresolvedQuestions: [
      "是否还需要更强的中文非目标词表。",
    ],
    nextStep: "补齐 mixed-language fixtures。",
    risks: [
      "如果把“不要破坏测试”误判成 non-goal，会丢失关键约束。",
    ],
  });

  assert.equal(payload.validation.ok, true, JSON.stringify(payload.validation, null, 2));
  assert.match(payload.markdown, /把 Jenny feedback workflow 转成可执行流程。/);
  assert.match(payload.markdown, /Structured verifier 已经接入。/);
  assert.match(payload.markdown, /不要破坏测试/);
});
