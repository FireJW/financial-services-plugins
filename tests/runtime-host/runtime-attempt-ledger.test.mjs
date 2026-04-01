import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  appendRuntimeAttemptLedgerEntry,
  buildRuntimeAttemptLedgerEntry,
  buildRuntimeAttemptScorecard,
  createRuntimeRunId,
  deriveRuntimeTaskId,
  loadRuntimeAttemptLedger,
} from "../../scripts/runtime/runtime-attempt-ledger-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const summaryScript = path.join(
  repoRoot,
  "scripts",
  "runtime",
  "summarize-runtime-attempt-ledger.mjs",
);

test("runtime attempt ledger entry captures validation failures and retry metadata", () => {
  const entry = buildRuntimeAttemptLedgerEntry({
    runId: "worker-jenny-001",
    taskId: "jenny-feedback",
    profile: "worker",
    attempt: 1,
    maxAttempts: 2,
    prompt: "First attempt prompt",
    timeoutMs: 30_000,
    maxTurns: 4,
    outputPath: "runtime-state/jenny-worker-output.md",
    result: {
      status: 0,
      signal: null,
      stdout: "## Conclusion\n\n- Missing sections.\n",
      stderr: "",
    },
    validationReport: {
      ok: false,
      verdict: "FAIL",
      checklist: [
        { name: "required_sections", ok: false, detail: "Missing sections: Risks" },
      ],
      missingFields: [],
      invalidFields: [],
      hasAdversarialProbe: null,
    },
    skipValidation: false,
    maxTurnsReached: false,
    willRetry: true,
    retryReason: "previous attempt violated the worker contract",
    nextMaxTurns: null,
    startedAtMs: 1_000,
    finishedAtMs: 1_250,
  });

  assert.equal(entry.schemaVersion, "runtime-attempt-ledger-v1");
  assert.equal(entry.attemptOutcome, "validation_failed");
  assert.equal(entry.retry.willRetry, true);
  assert.equal(entry.retry.reason, "previous attempt violated the worker contract");
  assert.deepEqual(entry.validation.failingChecks, ["required_sections"]);
  assert.equal(entry.durationMs, 250);
});

test("runtime attempt ledger round-trips ndjson entries", () => {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "runtime-ledger-"));
  const ledgerPath = path.join(tempDir, "attempts.ndjson");

  try {
    const runId = createRuntimeRunId("worker", "jenny-feedback");
    appendRuntimeAttemptLedgerEntry(
      ledgerPath,
      buildRuntimeAttemptLedgerEntry({
        runId,
        taskId: deriveRuntimeTaskId({ sourcePath: "runtime-state/jenny-feedback-task.md" }),
        profile: "worker",
        attempt: 1,
        maxAttempts: 1,
        prompt: "Prompt body",
        timeoutMs: 20_000,
        maxTurns: 4,
        outputPath: "runtime-state/jenny-worker-output.md",
        result: {
          status: 0,
          signal: null,
          stdout: "## Conclusion\n\n- Ship it.\n",
          stderr: "",
        },
        validationReport: {
          ok: true,
          verdict: "PASS",
          checklist: [],
          missingFields: [],
          invalidFields: [],
          hasAdversarialProbe: null,
        },
        skipValidation: false,
        maxTurnsReached: false,
        willRetry: false,
        retryReason: null,
        nextMaxTurns: null,
        startedAtMs: 2_000,
        finishedAtMs: 2_050,
      }),
    );

    const loaded = loadRuntimeAttemptLedger(ledgerPath);

    assert.equal(loaded.length, 1);
    assert.equal(loaded[0].taskId, "jenny-feedback-task");
    assert.equal(loaded[0].attemptOutcome, "success");
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runtime attempt scorecard groups retrying and successful runs", () => {
  const entries = [
    buildRuntimeAttemptLedgerEntry({
      runId: "worker-run-1",
      taskId: "jenny-feedback",
      profile: "worker",
      attempt: 1,
      maxAttempts: 2,
      prompt: "Attempt 1",
      timeoutMs: 20_000,
      maxTurns: 4,
      outputPath: "runtime-state/jenny-worker-output.md",
      result: { status: 0, signal: null, stdout: "", stderr: "" },
      validationReport: null,
      skipValidation: false,
      maxTurnsReached: false,
      willRetry: true,
      retryReason: "previous attempt returned empty stdout",
      nextMaxTurns: 8,
      startedAtMs: 0,
      finishedAtMs: 100,
    }),
    buildRuntimeAttemptLedgerEntry({
      runId: "worker-run-1",
      taskId: "jenny-feedback",
      profile: "worker",
      attempt: 2,
      maxAttempts: 2,
      prompt: "Attempt 2",
      timeoutMs: 20_000,
      maxTurns: 8,
      outputPath: "runtime-state/jenny-worker-output.md",
      result: { status: 0, signal: null, stdout: "## Conclusion\n\n- Done.\n", stderr: "" },
      validationReport: {
        ok: true,
        verdict: "PASS",
        checklist: [],
        missingFields: [],
        invalidFields: [],
        hasAdversarialProbe: null,
      },
      skipValidation: false,
      maxTurnsReached: false,
      willRetry: false,
      retryReason: null,
      nextMaxTurns: null,
      startedAtMs: 100,
      finishedAtMs: 280,
    }),
    buildRuntimeAttemptLedgerEntry({
      runId: "verifier-run-1",
      taskId: "jenny-feedback",
      profile: "verifier",
      attempt: 1,
      maxAttempts: 1,
      prompt: "Verifier attempt",
      timeoutMs: 20_000,
      maxTurns: 4,
      outputPath: "runtime-state/jenny-verifier-output.md",
      structuredOutputPath: "runtime-state/jenny-verifier-output.json",
      structuredVerifier: true,
      result: { status: 0, signal: null, stdout: "{\"schemaVersion\":\"structured-verifier-v1\"}", stderr: "" },
      validationReport: {
        ok: false,
        verdict: null,
        checklist: [{ name: "json_parse", ok: false, detail: "bad json" }],
        missingFields: [],
        invalidFields: [],
        parseError: "Unexpected end of JSON input",
        hasAdversarialProbe: false,
      },
      skipValidation: false,
      maxTurnsReached: false,
      willRetry: false,
      retryReason: null,
      nextMaxTurns: null,
      startedAtMs: 300,
      finishedAtMs: 360,
    }),
  ];

  const scorecard = buildRuntimeAttemptScorecard(entries, {
    inputFile: "runtime-state/runtime-attempts.ndjson",
  });

  assert.equal(scorecard.totalRuns, 2);
  assert.equal(scorecard.successRuns, 1);
  assert.equal(scorecard.retryingRuns, 1);
  assert.equal(scorecard.profiles.worker.successRuns, 1);
  assert.equal(scorecard.profiles.verifier.failedRuns, 1);
  assert.equal(scorecard.outcomeCounts.success, 1);
  assert.equal(scorecard.outcomeCounts.validation_failed, 1);
  assert.equal(scorecard.retryReasonCounts["previous attempt returned empty stdout"], 1);
});

test("runtime attempt scorecard script renders text and json", () => {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "runtime-scorecard-"));
  const ledgerPath = path.join(tempDir, "attempts.ndjson");

  try {
    appendRuntimeAttemptLedgerEntry(
      ledgerPath,
      buildRuntimeAttemptLedgerEntry({
        runId: "worker-run-2",
        taskId: "jenny-feedback",
        profile: "worker",
        attempt: 1,
        maxAttempts: 1,
        prompt: "Attempt 1",
        timeoutMs: 20_000,
        maxTurns: 4,
        outputPath: "runtime-state/jenny-worker-output.md",
        result: { status: 0, signal: null, stdout: "## Conclusion\n\n- Done.\n", stderr: "" },
        validationReport: {
          ok: true,
          verdict: "PASS",
          checklist: [],
          missingFields: [],
          invalidFields: [],
          hasAdversarialProbe: null,
        },
        skipValidation: false,
        maxTurnsReached: false,
        willRetry: false,
        retryReason: null,
        nextMaxTurns: null,
        startedAtMs: 1_000,
        finishedAtMs: 1_120,
      }),
    );

    const textResult = spawnSync(
      "node",
      [summaryScript, "--input", ledgerPath, "--format", "text"],
      {
        cwd: repoRoot,
        encoding: "utf8",
        timeout: 20_000,
      },
    );
    assert.equal(textResult.status, 0, textResult.stderr || textResult.stdout);
    assert.match(textResult.stdout, /Runtime Attempt Scorecard/);
    assert.match(textResult.stdout, /worker-run-2/);

    const jsonOutputPath = path.join(tempDir, "scorecard.json");
    const jsonResult = spawnSync(
      "node",
      [summaryScript, "--input", ledgerPath, "--json", "--output", jsonOutputPath],
      {
        cwd: repoRoot,
        encoding: "utf8",
        timeout: 20_000,
      },
    );
    assert.equal(jsonResult.status, 0, jsonResult.stderr || jsonResult.stdout);
    const scorecard = JSON.parse(readFileSync(jsonOutputPath, "utf8"));
    assert.equal(scorecard.schemaVersion, "runtime-attempt-scorecard-v1");
    assert.equal(scorecard.totalRuns, 1);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});
