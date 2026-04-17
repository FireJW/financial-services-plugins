import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const scriptPath = path.join(repoRoot, "scripts", "runtime", "run-real-task.mjs");

test("run-real-task entrypoint emits stable dry-run json output", () => {
  const outputDir = mkdtempSync(path.join(os.tmpdir(), "runtime-real-task-entry-"));

  try {
    const result = spawnSync(
      "node",
      [
        scriptPath,
        "--dry-run",
        "--json",
        "--input-file",
        "tests/fixtures/runtime-real-tasks/jenny-feedback-workflow/task.md",
        "--session-file",
        "tests/fixtures/runtime-state/sample-session-input.json",
        "--context-file",
        "tests/fixtures/runtime-real-tasks/jenny-feedback-workflow/evidence.md",
        "--output-dir",
        outputDir,
      ],
      {
        cwd: repoRoot,
        encoding: "utf8",
        timeout: 20_000,
      },
    );

    assert.equal(result.status, 0, result.stderr || result.stdout);
    const payload = JSON.parse(result.stdout);

    assert.equal(payload.schemaVersion, "real-task-runner-v1");
    assert.equal(payload.mode, "preview");
    assert.equal(payload.routePlan.routeId, "feedback_workflow");
    assert.equal(payload.structuredVerifier, true);
    assert.equal(payload.outputDir, outputDir);
    assert.match(payload.commands.worker.displayCommand, /run-worker-task\.mjs/);
    assert.match(payload.commands.verifier.displayCommand, /run-verifier-task\.mjs/);
    assert.match(
      payload.commands.verifierPreflight.displayCommand,
      /--local-only/,
    );
    assert.match(
      payload.artifacts.verifierStructuredOutputPath,
      /verifier-output\.json$/,
    );
  } finally {
    rmSync(outputDir, { recursive: true, force: true });
  }
});

test("run-real-task entrypoint lets callers disable structured verifier mode", () => {
  const outputDir = mkdtempSync(path.join(os.tmpdir(), "runtime-real-task-entry-"));

  try {
    const result = spawnSync(
      "node",
      [
        scriptPath,
        "--dry-run",
        "--json",
        "--request",
        "Verify the latest event update and tell me whether the newest report changed the picture.",
        "--output-dir",
        outputDir,
        "--no-structured-verifier",
      ],
      {
        cwd: repoRoot,
        encoding: "utf8",
        timeout: 20_000,
      },
    );

    assert.equal(result.status, 0, result.stderr || result.stdout);
    const payload = JSON.parse(result.stdout);

    assert.equal(payload.structuredVerifier, false);
    assert.equal(payload.routePlan.routeId, "classic_case");
    assert.equal(payload.routePlan.classicCaseId, "latest-event-verification");
    assert.equal(payload.artifacts.verifierStructuredOutputPath, null);
  } finally {
    rmSync(outputDir, { recursive: true, force: true });
  }
});
