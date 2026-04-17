import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildRetryPrompt,
  bumpMaxTurnsCliArgs,
  getMaxTurnsFromCliArgs,
  normalizeWorkerOutputForVerification,
  parseVerifierOutput,
} from "../../scripts/runtime/orchestration-lib.mjs";
import { writeRuntimeOutputFile } from "../../scripts/runtime/runtime-report-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const workerScript = path.join(repoRoot, "scripts", "runtime", "run-worker-task.mjs");
const verifierScript = path.join(repoRoot, "scripts", "runtime", "run-verifier-task.mjs");

test("worker entrypoint dry-run builds a real worker invocation payload", () => {
  const result = spawnSync(
    "node",
    [
      workerScript,
      "--task-file",
      "tests/fixtures/runtime-entrypoints/worker-task.md",
      "--task-id",
      "worker-dry-run",
      "--now-file",
      "tests/fixtures/runtime-entrypoints/sample-now.md",
      "--intent-file",
      "tests/fixtures/runtime-state/sample-user-intent.md",
      "--attempt-ledger-file",
      "runtime-state/test-worker-ledger.ndjson",
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

  assert.equal(payload.profile.name, "worker");
  assert.match(payload.prompt, /## Active Task/);
  assert.match(payload.prompt, /## Intent Snapshot/);
  assert.match(payload.prompt, /## Session Snapshot/);
  assert.match(payload.prompt, /## Required Output Shape/);
  assert.equal(payload.taskId, "worker-dry-run");
  assert.match(payload.attemptLedgerPath, /test-worker-ledger\.ndjson$/);
  assert.equal(typeof payload.promptBudgetReport?.riskLevel, "string");
  assert.ok(payload.invocation.cliArgs.includes("--print"), result.stdout);
  assert.ok(payload.invocation.cliArgs.includes("--output-format"), result.stdout);
});

test("verifier entrypoint local-only mode runs deterministic preflight", () => {
  const result = spawnSync(
    "node",
    [
      verifierScript,
      "--original-task-file",
      "tests/fixtures/runtime-entrypoints/verifier-original-task.md",
      "--worker-output-file",
      "tests/fixtures/runtime-orchestration/worker-output-valid.md",
      "--files-changed-file",
      "tests/fixtures/runtime-entrypoints/files-changed.txt",
      "--approach-file",
      "tests/fixtures/runtime-entrypoints/verifier-approach.md",
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

test("verifier entrypoint fails fast on invalid worker output in local-only mode", () => {
  const result = spawnSync(
    "node",
    [
      verifierScript,
      "--original-task",
      "Verify the wrapper output.",
      "--worker-output-file",
      "tests/fixtures/runtime-orchestration/worker-output-invalid.md",
      "--local-only",
      "--json",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 1, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.preflight.ok, false);
  assert.deepEqual(payload.preflight.missingSections, ["Risks"]);
});

test("verifier entrypoint dry-run builds a prompt with worker context and preflight", () => {
  const result = spawnSync(
    "node",
    [
      verifierScript,
      "--original-task-file",
      "tests/fixtures/runtime-entrypoints/verifier-original-task.md",
      "--worker-output-file",
      "tests/fixtures/runtime-orchestration/worker-output-valid.md",
      "--files-changed-file",
      "tests/fixtures/runtime-entrypoints/files-changed.txt",
      "--approach-file",
      "tests/fixtures/runtime-entrypoints/verifier-approach.md",
      "--task-id",
      "verifier-dry-run",
      "--attempt-ledger-file",
      "runtime-state/test-verifier-ledger.ndjson",
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

  assert.equal(payload.profile.name, "verifier");
  assert.match(payload.prompt, /## Original Task/);
  assert.match(payload.prompt, /## Worker Output/);
  assert.match(payload.prompt, /## Files Changed/);
  assert.match(payload.prompt, /## Deterministic Preflight/);
  assert.equal(payload.taskId, "verifier-dry-run");
  assert.match(payload.attemptLedgerPath, /test-verifier-ledger\.ndjson$/);
  assert.equal(typeof payload.promptBudgetReport?.riskLevel, "string");
});

test("verifier output parser accepts a valid structured verifier report", () => {
  const fixturePath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "verifier-output-valid.md",
  );
  const report = parseVerifierOutput(readFileSync(fixturePath, "utf8"));

  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, "PASS");
  assert.equal(report.hasAdversarialProbe, true);
  assert.equal(report.checks.length, 2);
});

test("verifier output parser accepts '**Result:** PASS' field style", () => {
  const report = parseVerifierOutput(`
### Check: Contract scan
**Command run:** local contract validation
**Output observed:** All required sections are present.
**Result:** PASS

### Check: Adversarial overclaim probe
**Command run:** compare Confirmed and Unconfirmed certainty levels
**Output observed:** No unsupported upgrade from summary to direct quote.
**Result:** PASS

VERDICT: PASS
`);

  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, "PASS");
  assert.equal(report.hasAdversarialProbe, true);
  assert.equal(report.checks.length, 2);
});

test("runtime output helper persists UTF-8 output safely", () => {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "runtime-output-"));
  const outputPath = path.join(tempDir, "worker-output.md");
  const content = "## Conclusion\n\n- UTF-8 output should stay readable.\n";

  try {
    writeRuntimeOutputFile(outputPath, content);
    assert.equal(readFileSync(outputPath, "utf8"), content);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("worker normalization strips preamble before contract headings", () => {
  const normalized = normalizeWorkerOutputForVerification(
    "Preamble text\n\n## Conclusion\n- Main answer\n\n## Confirmed\n- Fact\n\n## Unconfirmed\n- None.\n\n## Risks\n- None.\n\n## Next Step\n- Ship it.\n",
  );

  assert.match(normalized, /^## Conclusion/);
  assert.doesNotMatch(normalized, /^Preamble/);
});

test("retry prompt adds explicit contract reminders", () => {
  const workerRetry = buildRetryPrompt("Base prompt", {
    kind: "worker",
    attempt: 2,
    reason: "previous attempt violated the worker contract",
  });
  const verifierRetry = buildRetryPrompt("Base prompt", {
    kind: "verifier",
    attempt: 3,
    reason: "previous attempt returned empty stdout",
  });

  assert.match(workerRetry, /Start immediately with `## Conclusion`/);
  assert.match(verifierRetry, /Start immediately with `### Check:`/);
  assert.match(verifierRetry, /End with `VERDICT: PASS`, `VERDICT: FAIL`, or `VERDICT: PARTIAL`/);
});

test("max-turn bump helper replaces existing max-turn setting", () => {
  const bumped = bumpMaxTurnsCliArgs(
    ["--print", "--max-turns", "4", "--output-format", "text"],
    8,
  );

  assert.deepEqual(bumped, ["--print", "--max-turns", "8", "--output-format", "text"]);
});

test("max-turn helpers respect the last explicit max-turn flag", () => {
  const cliArgs = ["--print", "--max-turns", "4", "--output-format", "text", "--max-turns", "6"];

  assert.equal(getMaxTurnsFromCliArgs(cliArgs), 6);
  assert.deepEqual(
    bumpMaxTurnsCliArgs(cliArgs, 8),
    ["--print", "--max-turns", "4", "--output-format", "text", "--max-turns", "8"],
  );
});
