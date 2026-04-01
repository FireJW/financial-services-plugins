import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

export const RUNTIME_ATTEMPT_LEDGER_SCHEMA_VERSION = "runtime-attempt-ledger-v1";
export const RUNTIME_ATTEMPT_SCORECARD_SCHEMA_VERSION = "runtime-attempt-scorecard-v1";

export function deriveRuntimeTaskId(options = {}) {
  const explicitTaskId = sanitizeTaskId(options.explicitTaskId);
  if (explicitTaskId) {
    return explicitTaskId;
  }

  const sourcePath = `${options.sourcePath ?? ""}`.trim();
  if (sourcePath) {
    const parsed = path.parse(sourcePath);
    const derivedTaskId = sanitizeTaskId(parsed.name);
    if (derivedTaskId) {
      return derivedTaskId;
    }
  }

  return sanitizeTaskId(options.fallback) ?? "runtime-task";
}

export function createRuntimeRunId(profile, taskId) {
  const safeProfile = sanitizeTaskId(profile) ?? "runtime";
  const safeTaskId = sanitizeTaskId(taskId) ?? "task";
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const entropy = Math.random().toString(36).slice(2, 8);
  return `${safeProfile}-${safeTaskId}-${timestamp}-${entropy}`;
}

export function buildRuntimeAttemptLedgerEntry(options = {}) {
  const stdout = `${options.result?.stdout ?? ""}`;
  const stderr = `${options.result?.stderr ?? ""}`;
  const hasContent = Boolean(stdout.trim());
  const validation = buildValidationSummary(options.validationReport, options.skipValidation);
  const maxTurns = Number.isFinite(options.maxTurns) ? options.maxTurns : null;
  const nextMaxTurns = Number.isFinite(options.nextMaxTurns) ? options.nextMaxTurns : null;

  return {
    schemaVersion: RUNTIME_ATTEMPT_LEDGER_SCHEMA_VERSION,
    runId: options.runId ?? null,
    taskId: options.taskId ?? null,
    profile: options.profile ?? null,
    attempt: Number.isFinite(options.attempt) ? options.attempt : null,
    maxAttempts: Number.isFinite(options.maxAttempts) ? options.maxAttempts : null,
    startedAt: toIsoString(options.startedAtMs),
    finishedAt: toIsoString(options.finishedAtMs),
    durationMs: resolveDurationMs(options.startedAtMs, options.finishedAtMs),
    promptChars: `${options.prompt ?? ""}`.length,
    promptLines: countPromptLines(options.prompt),
    invocation: {
      maxTurns,
      timeoutMs: Number.isFinite(options.timeoutMs) ? options.timeoutMs : null,
      structuredVerifier: Boolean(options.structuredVerifier),
    },
    promptBudget: options.promptBudget ?? null,
    artifacts: {
      outputPath: options.outputPath ?? null,
      structuredOutputPath: options.structuredOutputPath ?? null,
    },
    result: {
      status: options.result?.status ?? null,
      signal: options.result?.signal ?? null,
      stdoutChars: stdout.length,
      stderrChars: stderr.length,
      emptyStdout: !hasContent,
      maxTurnsReached: Boolean(options.maxTurnsReached),
    },
    validation,
    retry: {
      willRetry: Boolean(options.willRetry),
      reason: options.retryReason ?? null,
      nextMaxTurns,
    },
    attemptOutcome: classifyAttemptOutcome({
      status: options.result?.status ?? null,
      hasContent,
      maxTurnsReached: Boolean(options.maxTurnsReached),
      validation,
    }),
    finalAttempt: !options.willRetry,
  };
}

export function appendRuntimeAttemptLedgerEntry(filePath, entry) {
  if (!filePath) {
    return entry;
  }

  const resolvedPath = path.resolve(filePath);
  mkdirSync(path.dirname(resolvedPath), { recursive: true });
  appendFileSync(resolvedPath, `${JSON.stringify(entry)}\n`, "utf8");
  return entry;
}

export function parseRuntimeAttemptLedger(text = "") {
  return `${text ?? ""}`
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

export function loadRuntimeAttemptLedger(filePath) {
  if (!filePath || !existsSync(filePath)) {
    return [];
  }

  return parseRuntimeAttemptLedger(readFileSync(filePath, "utf8"));
}

export function buildRuntimeAttemptScorecard(entries = [], options = {}) {
  const normalizedEntries = [...entries]
    .filter((entry) => entry && typeof entry === "object")
    .filter((entry) => !entry.schemaVersion || entry.schemaVersion === RUNTIME_ATTEMPT_LEDGER_SCHEMA_VERSION)
    .sort((left, right) => {
      const runIdCompare = `${left.runId ?? ""}`.localeCompare(`${right.runId ?? ""}`);
      if (runIdCompare !== 0) {
        return runIdCompare;
      }
      return (left.attempt ?? 0) - (right.attempt ?? 0);
    });

  const runsById = new Map();
  for (const entry of normalizedEntries) {
    const runId = `${entry.runId ?? "unknown-run"}`;
    if (!runsById.has(runId)) {
      runsById.set(runId, []);
    }
    runsById.get(runId).push(entry);
  }

  const runs = [...runsById.values()].map((runEntries) => summarizeRun(runEntries));
  const profileNames = [...new Set(runs.map((run) => run.profile).filter(Boolean))].sort();
  const profiles = Object.fromEntries(
    profileNames.map((profileName) => [
      profileName,
      summarizeProfile(runs.filter((run) => run.profile === profileName)),
    ]),
  );
  const outcomeCounts = countBy(runs, (run) => run.finalOutcome ?? "unknown");
  const retryReasonCounts = countBy(
    normalizedEntries.filter((entry) => entry.retry?.willRetry),
    (entry) => entry.retry?.reason ?? "unknown",
  );

  return {
    schemaVersion: RUNTIME_ATTEMPT_SCORECARD_SCHEMA_VERSION,
    inputFile: options.inputFile ?? null,
    generatedAt: new Date().toISOString(),
    totalEntries: normalizedEntries.length,
    totalRuns: runs.length,
    successRuns: runs.filter((run) => run.finalOutcome === "success").length,
    retryingRuns: runs.filter((run) => run.hadRetry).length,
    profiles,
    outcomeCounts,
    retryReasonCounts,
    runs,
  };
}

export function renderRuntimeAttemptScorecardText(scorecard) {
  const lines = [];
  lines.push("Runtime Attempt Scorecard");
  lines.push(`- total_runs: ${scorecard.totalRuns}`);
  lines.push(`- total_entries: ${scorecard.totalEntries}`);
  lines.push(`- success_runs: ${scorecard.successRuns}`);
  lines.push(`- retrying_runs: ${scorecard.retryingRuns}`);

  if (scorecard.inputFile) {
    lines.push(`- input_file: ${scorecard.inputFile}`);
  }

  lines.push("");
  lines.push("Profiles");
  for (const [profileName, profileSummary] of Object.entries(scorecard.profiles ?? {})) {
    lines.push(
      `- ${profileName}: runs=${profileSummary.runs}, success=${profileSummary.successRuns}, failed=${profileSummary.failedRuns}, retrying=${profileSummary.retryingRuns}, avg_attempts=${profileSummary.avgAttempts}, avg_duration_ms=${profileSummary.avgDurationMs}`,
    );
  }

  lines.push("");
  lines.push("Outcome Counts");
  for (const [outcome, count] of Object.entries(scorecard.outcomeCounts ?? {})) {
    lines.push(`- ${outcome}: ${count}`);
  }

  if (Object.keys(scorecard.retryReasonCounts ?? {}).length > 0) {
    lines.push("");
    lines.push("Retry Reasons");
    for (const [reason, count] of Object.entries(scorecard.retryReasonCounts)) {
      lines.push(`- ${reason}: ${count}`);
    }
  }

  if ((scorecard.runs ?? []).length > 0) {
    lines.push("");
    lines.push("Runs");
    for (const run of scorecard.runs) {
      lines.push(
        `- ${run.runId}: profile=${run.profile}, task=${run.taskId}, attempts=${run.attempts}, final=${run.finalOutcome}, verdict=${run.finalVerdict ?? "n/a"}, retry=${run.hadRetry ? "yes" : "no"}`,
      );
    }
  }

  return `${lines.join("\n")}\n`;
}

function summarizeRun(runEntries) {
  const sortedEntries = [...runEntries].sort((left, right) => (left.attempt ?? 0) - (right.attempt ?? 0));
  const finalEntry = sortedEntries[sortedEntries.length - 1];
  const profile = finalEntry.profile ?? sortedEntries[0]?.profile ?? null;
  const taskId = finalEntry.taskId ?? sortedEntries[0]?.taskId ?? null;

  return {
    runId: finalEntry.runId ?? null,
    profile,
    taskId,
    attempts: sortedEntries.length,
    hadRetry: sortedEntries.length > 1,
    totalDurationMs: sortedEntries.reduce((sum, entry) => sum + (entry.durationMs ?? 0), 0),
    finalOutcome: finalEntry.attemptOutcome ?? null,
    finalVerdict: finalEntry.validation?.verdict ?? null,
    retryReasons: sortedEntries
      .filter((entry) => entry.retry?.willRetry && entry.retry?.reason)
      .map((entry) => entry.retry.reason),
    entries: sortedEntries,
  };
}

function summarizeProfile(runs) {
  const runCount = runs.length;
  const successRuns = runs.filter((run) => run.finalOutcome === "success").length;
  const retryingRuns = runs.filter((run) => run.hadRetry).length;
  const totalAttempts = runs.reduce((sum, run) => sum + run.attempts, 0);
  const totalDurationMs = runs.reduce((sum, run) => sum + run.totalDurationMs, 0);

  return {
    runs: runCount,
    successRuns,
    failedRuns: runCount - successRuns,
    retryingRuns,
    avgAttempts: runCount > 0 ? roundNumber(totalAttempts / runCount) : 0,
    avgDurationMs: runCount > 0 ? roundNumber(totalDurationMs / runCount) : 0,
  };
}

function buildValidationSummary(validationReport, skipValidation) {
  if (skipValidation) {
    return {
      skipped: true,
      ok: null,
      verdict: null,
      failingChecks: [],
      missingFields: [],
      invalidFields: [],
      parseError: null,
      hasAdversarialProbe: null,
    };
  }

  return {
    skipped: false,
    ok: validationReport?.ok ?? null,
    verdict: validationReport?.verdict ?? null,
    failingChecks: (validationReport?.checklist ?? [])
      .filter((item) => !item.ok)
      .map((item) => item.name),
    missingFields: [...(validationReport?.missingFields ?? [])],
    invalidFields: [...(validationReport?.invalidFields ?? [])],
    parseError: validationReport?.parseError ?? null,
    hasAdversarialProbe: validationReport?.hasAdversarialProbe ?? null,
  };
}

function classifyAttemptOutcome(options) {
  if ((options.status ?? 1) !== 0) {
    return options.maxTurnsReached ? "max_turns_runtime_error" : "runtime_error";
  }

  if (!options.hasContent) {
    return "empty_stdout";
  }

  if (options.validation.skipped) {
    return "success";
  }

  return options.validation.ok ? "success" : "validation_failed";
}

function sanitizeTaskId(value) {
  const trimmed = `${value ?? ""}`.trim();
  if (!trimmed) {
    return null;
  }

  const normalized = trimmed
    .replace(/[\\/]+/g, "-")
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return normalized || null;
}

function countPromptLines(prompt) {
  const normalized = `${prompt ?? ""}`;
  if (!normalized) {
    return 0;
  }
  return normalized.split(/\r?\n/).length;
}

function toIsoString(value) {
  return Number.isFinite(value) ? new Date(value).toISOString() : null;
}

function resolveDurationMs(startedAtMs, finishedAtMs) {
  if (!Number.isFinite(startedAtMs) || !Number.isFinite(finishedAtMs)) {
    return null;
  }

  return Math.max(0, finishedAtMs - startedAtMs);
}

function roundNumber(value) {
  return Number.isFinite(value) ? Math.round(value * 100) / 100 : 0;
}

function countBy(items, getKey) {
  const counts = {};

  for (const item of items) {
    const key = `${getKey(item) ?? "unknown"}`;
    counts[key] = (counts[key] ?? 0) + 1;
  }

  return counts;
}
