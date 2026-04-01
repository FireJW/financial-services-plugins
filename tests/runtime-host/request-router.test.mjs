import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { routeRequest } from "../../scripts/runtime/request-router-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const scriptPath = path.join(repoRoot, "scripts", "runtime", "route-request.mjs");

test("request router matches feedback workflow tasks", () => {
  const plan = routeRequest(
    "Collect what Jenny Wen said in interviews and podcasts about using AI with user feedback, then turn it into a workflow SOP and weekly cadence.",
  );

  assert.equal(plan.routeId, "feedback_workflow");
  assert.equal(plan.profile, "worker");
  assert.ok(plan.matchedSignals.some((signal) => signal.kind === "feedback_keyword"));
  assert.ok(
    plan.nativeWorkflow.some((item) => item.includes("feedback-iteration-workflow")),
    JSON.stringify(plan, null, 2),
  );
});

test("request router matches all classic case families", () => {
  const cases = [
    {
      request: "Verify the latest event update and tell me whether the newest report changed the picture.",
      expected: "latest-event-verification",
      profile: "explore",
    },
    {
      request: "Turn this X thread into evidence and separate the actual post text from inference.",
      expected: "x-post-evidence",
      profile: "explore",
    },
    {
      request: "Map this oil shock into beneficiaries and losers across the macro shock chain.",
      expected: "macro-shock-chain-map",
      profile: "worker",
    },
    {
      request: "Use the evidence pack to write an evidence-backed article draft.",
      expected: "evidence-to-article",
      profile: "worker",
    },
    {
      request: "Improve this repeated workflow and show me the workflow improvement loop.",
      expected: "workflow-improvement-loop",
      profile: "worker",
    },
  ];

  for (const entry of cases) {
    const plan = routeRequest(entry.request);
    assert.equal(plan.routeId, "classic_case", JSON.stringify(plan, null, 2));
    assert.equal(plan.classicCaseId, entry.expected, JSON.stringify(plan, null, 2));
    assert.equal(plan.profile, entry.profile, JSON.stringify(plan, null, 2));
  }
});

test("request router matches a-share event research requests", () => {
  const plan = routeRequest(
    "比较两只A股在政策冲击下谁更像主题炒作、谁更像业绩驱动，并解释为什么它们不再跟随商品价格。",
  );

  assert.equal(plan.routeId, "a_share_event_research");
  assert.equal(plan.profile, "worker");
  assert.ok(
    plan.pluginDirs.some((pluginDir) => /equity-research$/i.test(pluginDir)),
    JSON.stringify(plan, null, 2),
  );
});

test("request router falls back to explore for generic search-like requests", () => {
  const plan = routeRequest("Search the repo and tell me which plugin mentions browser automation.");

  assert.equal(plan.routeId, "fallback_search");
  assert.equal(plan.profile, "explore");
});

test("request router lets explicit overrides win over automatic routing", () => {
  const plan = routeRequest(
    "Collect what Jenny Wen said in interviews and turn it into a workflow.",
    {
      routeId: "classic_case",
      classicCaseId: "workflow-improvement-loop",
      profile: "verifier",
      pluginDirs: ["financial-analysis"],
    },
  );

  assert.equal(plan.routeId, "classic_case");
  assert.equal(plan.classicCaseId, "workflow-improvement-loop");
  assert.equal(plan.profile, "verifier");
  assert.ok(plan.overrideApplied.routeId);
  assert.ok(plan.overrideApplied.profile);
  assert.ok(plan.overrideApplied.pluginDirs);
});

test("route-request entrypoint emits stable dry-run json output", () => {
  const result = spawnSync(
    "node",
    [
      scriptPath,
      "--json",
      "--request",
      "Collect what this design leader said in interviews and support tickets, then turn it into a workflow cadence.",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.routeId, "feedback_workflow");
  assert.equal(payload.profile, "worker");
  assert.match(payload.nextInvocation.displayCommand, /run-task-profile\.mjs/);
});
