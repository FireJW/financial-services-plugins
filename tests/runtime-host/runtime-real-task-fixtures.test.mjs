import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const workerScript = path.join(repoRoot, "scripts", "runtime", "run-worker-task.mjs");
const verifierScript = path.join(repoRoot, "scripts", "runtime", "run-verifier-task.mjs");
const fixtureRoot = path.join(
  "tests",
  "fixtures",
  "runtime-real-tasks",
  "jenny-feedback-workflow",
);

test("real-task worker dry-run exposes budget report and keeps evidence context", () => {
  const result = spawnSync(
    "node",
    [
      workerScript,
      "--task-file",
      path.join(fixtureRoot, "task.md"),
      "--intent-file",
      path.join(fixtureRoot, "intent.md"),
      "--now-file",
      path.join(fixtureRoot, "now.md"),
      "--context-file",
      path.join(fixtureRoot, "evidence.md"),
      "--dry-run",
      "--json",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.taskId, "task");
  assert.match(payload.prompt, /Jenny Wen/);
  assert.match(payload.prompt, /direct quote/);
  assert.ok(
    payload.promptBudgetReport.topSegments.some((segment) => segment.label.includes("evidence.md")),
    JSON.stringify(payload.promptBudgetReport, null, 2),
  );
});

test("real-task verifier local-only preflight passes on the Jenny workflow output", () => {
  const result = spawnSync(
    "node",
    [
      verifierScript,
      "--original-task-file",
      path.join(fixtureRoot, "task.md"),
      "--worker-output-file",
      path.join(fixtureRoot, "worker-output.md"),
      "--files-changed-file",
      path.join(fixtureRoot, "files-changed.txt"),
      "--approach-file",
      path.join(fixtureRoot, "verifier-approach.md"),
      "--local-only",
      "--json",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.mode, "local-only");
  assert.equal(payload.preflight.ok, true);
  assert.match(payload.preflightSummary, /VERDICT: PASS/);
});

test("real-task structured verifier dry-run shows worker output as a dominant segment", () => {
  const result = spawnSync(
    "node",
    [
      verifierScript,
      "--original-task-file",
      path.join(fixtureRoot, "task.md"),
      "--worker-output-file",
      path.join(fixtureRoot, "worker-output.md"),
      "--files-changed-file",
      path.join(fixtureRoot, "files-changed.txt"),
      "--approach-file",
      path.join(fixtureRoot, "verifier-approach.md"),
      "--intent-file",
      path.join(fixtureRoot, "intent.md"),
      "--now-file",
      path.join(fixtureRoot, "now.md"),
      "--structured-verifier",
      "--dry-run",
      "--json",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.structuredVerifier, true);
  assert.match(payload.prompt, /Return JSON only/);
  assert.ok(
    payload.promptBudgetReport.topSegments.some((segment) => segment.label === "Worker output"),
    JSON.stringify(payload.promptBudgetReport, null, 2),
  );
});
