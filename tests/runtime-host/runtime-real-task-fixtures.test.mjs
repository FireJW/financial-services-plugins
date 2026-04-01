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
const fixtureSpecs = [
  {
    name: "Jenny feedback workflow",
    fixtureRoot: path.join(
      "tests",
      "fixtures",
      "runtime-real-tasks",
      "jenny-feedback-workflow",
    ),
    promptPattern: /Jenny Wen/,
    evidencePattern: /direct quote/,
  },
  {
    name: "A-share macro shock chain map",
    fixtureRoot: path.join(
      "tests",
      "fixtures",
      "runtime-real-tasks",
      "a-share-macro-shock-chain-map",
    ),
    promptPattern: /A-share|中国海油/,
    evidencePattern: /physical disruption|risk premium/,
  },
];

for (const fixture of fixtureSpecs) {
  test(`real-task worker dry-run exposes budget report and keeps evidence context for ${fixture.name}`, () => {
    const result = spawnSync(
      "node",
      [
        workerScript,
        "--task-file",
        path.join(fixture.fixtureRoot, "task.md"),
        "--intent-file",
        path.join(fixture.fixtureRoot, "intent.md"),
        "--now-file",
        path.join(fixture.fixtureRoot, "now.md"),
        "--context-file",
        path.join(fixture.fixtureRoot, "evidence.md"),
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
    assert.match(payload.prompt, fixture.promptPattern);
    assert.match(payload.prompt, fixture.evidencePattern);
    assert.ok(
      payload.promptBudgetReport.topSegments.some((segment) => segment.label.includes("evidence.md")),
      JSON.stringify(payload.promptBudgetReport, null, 2),
    );
  });

  test(`real-task verifier local-only preflight passes for ${fixture.name}`, () => {
    const result = spawnSync(
      "node",
      [
        verifierScript,
        "--original-task-file",
        path.join(fixture.fixtureRoot, "task.md"),
        "--worker-output-file",
        path.join(fixture.fixtureRoot, "worker-output.md"),
        "--files-changed-file",
        path.join(fixture.fixtureRoot, "files-changed.txt"),
        "--approach-file",
        path.join(fixture.fixtureRoot, "verifier-approach.md"),
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

  test(`real-task structured verifier dry-run shows worker output as a dominant segment for ${fixture.name}`, () => {
    const result = spawnSync(
      "node",
      [
        verifierScript,
        "--original-task-file",
        path.join(fixture.fixtureRoot, "task.md"),
        "--worker-output-file",
        path.join(fixture.fixtureRoot, "worker-output.md"),
        "--files-changed-file",
        path.join(fixture.fixtureRoot, "files-changed.txt"),
        "--approach-file",
        path.join(fixture.fixtureRoot, "verifier-approach.md"),
        "--intent-file",
        path.join(fixture.fixtureRoot, "intent.md"),
        "--now-file",
        path.join(fixture.fixtureRoot, "now.md"),
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
}
