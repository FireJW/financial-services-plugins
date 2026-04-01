import { existsSync, readFileSync, writeFileSync } from "node:fs";
import process from "node:process";
import {
  buildRetryPrompt,
  buildTaskProfilePreview,
  buildWorkerPrompt,
  bumpMaxTurnsCliArgs,
  getMaxTurnsFromCliArgs,
  resolveRepoPath,
  validateWorkerOutput,
} from "./orchestration-lib.mjs";
import {
  appendRuntimeAttemptLedgerEntry,
  buildRuntimeAttemptLedgerEntry,
  createRuntimeRunId,
  deriveRuntimeTaskId,
} from "./runtime-attempt-ledger-lib.mjs";
import {
  applyPromptBudgetGuardrails,
  buildPromptBudgetReport,
  renderPromptBudgetReport,
} from "./runtime-prompt-budget-lib.mjs";
import { runRuntimeCli, writeRuntimeOutputFile } from "./runtime-report-lib.mjs";

const rawArgs = process.argv.slice(2);
const separatorIndex = rawArgs.indexOf("--");
const args = separatorIndex === -1 ? rawArgs : rawArgs.slice(0, separatorIndex);
const forwardedArgs = separatorIndex === -1 ? [] : rawArgs.slice(separatorIndex + 1);

const taskFilePath = readFlagValue(args, "--task-file");
const task = getRequiredText(args, "--task", "--task-file");
const taskId = deriveRuntimeTaskId({
  explicitTaskId: readFlagValue(args, "--task-id"),
  sourcePath: taskFilePath,
  fallback: "worker-inline-task",
});
const outputPath = readFlagValue(args, "--output");
const attemptLedgerPath = readFlagValue(args, "--attempt-ledger-file");
const format = normalizeFormat(args);
const nowMarkdown = readOptionalFile(getStateFilePath(args, "--now-file", "runtime-state/NOW.md"));
const intentMarkdown = readOptionalFile(getStateFilePath(args, "--intent-file", "runtime-state/INTENT.md"));
const contextFiles = readFlagValues(args, "--context-file").map((filePath) => ({
  label: `Context: ${filePath}`,
  content: readFileSync(resolveRepoPath(filePath), "utf8").trim(),
}));
const timeoutMs = Number.parseInt(readFlagValue(args, "--timeout-ms") ?? "", 10);
const maxAttempts = normalizeMaxAttempts(readFlagValue(args, "--max-attempts"));

const prompt = buildWorkerPrompt({
  task,
  nowMarkdown,
  intentMarkdown,
  contextItems: contextFiles,
});

const preview = buildTaskProfilePreview("worker", {
  pluginDirs: readFlagValues(args, "--plugin-dir"),
  allPlugins: args.includes("--all-plugins"),
  includePartnerBuilt: args.includes("--include-partner-built"),
  forwardedArgs: ensureHeadlessTextArgs(forwardedArgs),
});
const initialBudgetReport = buildPromptBudgetReport({
  profile: "worker",
  prompt,
  cliArgs: preview.invocation.cliArgs,
  segments: [
    { label: "Task", content: task },
    { label: "Intent", content: intentMarkdown },
    { label: "NOW", content: nowMarkdown },
    ...contextFiles.map((item) => ({ label: item.label, content: item.content })),
  ],
});
const promptBudgetGuardrail = applyPromptBudgetGuardrails(preview.invocation.cliArgs, initialBudgetReport, {
  allowAutoBump: !forwardedArgs.includes("--max-turns"),
});

if (args.includes("--dry-run")) {
  const payload = {
    ...preview,
    invocation: {
      ...preview.invocation,
      cliArgs: promptBudgetGuardrail.cliArgs,
    },
    prompt,
    taskId,
    attemptLedgerPath: attemptLedgerPath ? resolveRepoPath(attemptLedgerPath) : null,
    promptBudgetReport: initialBudgetReport,
    promptBudgetGuardrail,
  };
  writeOutput(payload, format, outputPath);
}

const resolvedOutputPath = outputPath ? resolveRepoPath(outputPath) : null;
const resolvedAttemptLedgerPath = attemptLedgerPath ? resolveRepoPath(attemptLedgerPath) : null;
const runId = resolvedAttemptLedgerPath ? createRuntimeRunId("worker", taskId) : null;
const execution = runWorkerWithRetries({
  cliArgs: promptBudgetGuardrail.cliArgs,
  prompt,
  timeoutMs,
  maxAttempts,
  skipValidation: args.includes("--skip-validation"),
  runId,
  taskId,
  outputPath: resolvedOutputPath,
  attemptLedgerPath: resolvedAttemptLedgerPath,
  promptBudgetReport: initialBudgetReport,
  promptBudgetGuardrailReason: promptBudgetGuardrail.reason,
  recordAttempt: resolvedAttemptLedgerPath
    ? (entry) => appendRuntimeAttemptLedgerEntry(resolvedAttemptLedgerPath, entry)
    : null,
});
const result = execution.result;
const validationReport = execution.validationReport;

if (resolvedOutputPath) {
  writeRuntimeOutputFile(resolvedOutputPath, result.stdout ?? "");
}

if (result.stdout) {
  process.stdout.write(result.stdout);
}
if (result.stderr) {
  process.stderr.write(result.stderr);
}

if ((result.status ?? 1) !== 0) {
  process.exit(result.status ?? 1);
}

if (!(result.stdout ?? "").trim()) {
  process.stderr.write("Runtime returned empty stdout for worker output.\n");
  process.exit(2);
}

if (!args.includes("--skip-validation")) {
  if (!validationReport?.ok) {
    process.stderr.write(`\nWorker output failed contract validation:\n`);
    for (const item of validationReport?.checklist ?? []) {
      process.stderr.write(`- ${item.name}: ${item.ok ? "PASS" : "FAIL"} - ${item.detail}\n`);
    }
    process.exit(2);
  }
}

process.exit(0);

function normalizeFormat(argv) {
  if (argv.includes("--json")) {
    return "json";
  }
  return readFlagValue(argv, "--format") ?? "json";
}

function ensureHeadlessTextArgs(forwarded) {
  const nextArgs = [...forwarded];
  if (!nextArgs.includes("--print") && !nextArgs.includes("-p")) {
    nextArgs.unshift("--print");
  }
  if (!nextArgs.includes("--output-format")) {
    nextArgs.push("--output-format", "text");
  }
  return nextArgs;
}

function getRequiredText(argv, inlineFlag, fileFlag) {
  const inlineValue = readFlagValue(argv, inlineFlag);
  if (inlineValue) {
    return inlineValue;
  }

  const fileValue = readFlagValue(argv, fileFlag);
  if (fileValue) {
    return readFileSync(resolveRepoPath(fileValue), "utf8").trim();
  }

  process.stderr.write(
    `Usage: node scripts/runtime/run-worker-task.mjs (${inlineFlag} <text> | ${fileFlag} <file>) [--task-id <id>] [--dry-run] [--json] [--now-file <file>] [--intent-file <file>] [--context-file <file>] [--output <file>] [--attempt-ledger-file <file>] [--timeout-ms <n>] [--max-attempts <n>] [--plugin-dir <path>] [--all-plugins] [--include-partner-built] [--skip-validation] [-- <runtime args...>]\n`,
  );
  process.exit(1);
}

function getStateFilePath(argv, flagName, defaultRelativePath) {
  const explicitPath = readFlagValue(argv, flagName);
  if (explicitPath) {
    return resolveRepoPath(explicitPath);
  }

  const defaultPath = resolveRepoPath(defaultRelativePath);
  return existsSync(defaultPath) ? defaultPath : null;
}

function readOptionalFile(filePath) {
  if (!filePath || !existsSync(filePath)) {
    return "";
  }
  return readFileSync(filePath, "utf8").trim();
}

function readFlagValue(argv, flagName) {
  const index = argv.indexOf(flagName);
  if (index === -1 || index === argv.length - 1) {
    return null;
  }
  return argv[index + 1];
}

function readFlagValues(argv, flagName) {
  const values = [];
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] !== flagName) {
      continue;
    }
    if (index === argv.length - 1) {
      process.stderr.write(`Missing value for ${flagName}.\n`);
      process.exit(1);
    }
    values.push(argv[index + 1]);
    index += 1;
  }
  return values;
}

function writeOutput(payload, format, outputPath) {
  const serialized =
    format === "text"
      ? `${payload.prompt}\n`
      : `${JSON.stringify(payload, null, 2)}\n`;

  if (outputPath) {
    writeFileSync(resolveRepoPath(outputPath), serialized, "utf8");
  } else {
    process.stdout.write(serialized);
  }
  process.exit(0);
}

function runWorkerWithRetries(options) {
  let attempt = 1;
  let attemptPrompt = options.prompt;
  let attemptCliArgs = [...options.cliArgs];
  let lastResult = null;
  let lastValidationReport = null;

  while (attempt <= options.maxAttempts) {
    const promptBudgetReport = buildPromptBudgetReport({
      profile: "worker",
      prompt: attemptPrompt,
      cliArgs: attemptCliArgs,
      segments: [{ label: "Worker prompt", content: attemptPrompt }],
    });
    if (attempt === 1 && options.promptBudgetReport?.riskLevel !== "ok") {
      process.stderr.write(renderPromptBudgetReport(options.promptBudgetReport));
      if (options.promptBudgetGuardrailReason) {
        process.stderr.write(`Budget guardrail: ${options.promptBudgetGuardrailReason}\n`);
      }
    }

    const startedAtMs = Date.now();
    const result = runRuntimeCli(attemptCliArgs, {
      timeout: Number.isFinite(options.timeoutMs) ? options.timeoutMs : undefined,
      input: attemptPrompt,
    });
    const finishedAtMs = Date.now();

    lastResult = result;
    const stdout = result.stdout ?? "";
    const stderr = result.stderr ?? "";
    const status = result.status ?? 1;
    const hasContent = Boolean(stdout.trim());
    const validationReport =
      status === 0 && hasContent && !options.skipValidation
        ? validateWorkerOutput(stdout)
        : null;

    lastValidationReport = validationReport;

    const maxTurnsReached = /Reached max turns/i.test(`${stderr}\n${stdout}`);
    const maxTurns = getMaxTurnsFromCliArgs(attemptCliArgs) ?? 4;
    const retryDetail =
      status !== 0
        ? compactFailureDetail(stderr || stdout || `exit status ${status}`)
        : !hasContent
          ? "runtime returned empty stdout"
          : validationReport && !validationReport.ok
            ? validationReport.checklist
                .filter((item) => !item.ok)
                .map((item) => `${item.name}: ${item.detail}`)
                .join("; ")
            : "";
    const retryReason =
      status !== 0 && maxTurnsReached
        ? "previous attempt reached max turns"
        : !hasContent
          ? "previous attempt returned empty stdout"
          : "previous attempt violated the worker contract";

    const shouldRetry =
      attempt < options.maxAttempts &&
      (
        (status !== 0 && maxTurnsReached) ||
        (status === 0 && !hasContent) ||
        (status === 0 && !options.skipValidation && validationReport && !validationReport.ok)
      );

    const nextMaxTurns =
      shouldRetry && (maxTurnsReached || !hasContent)
        ? maxTurns * 2
        : null;

    if (options.recordAttempt) {
      options.recordAttempt(
        buildRuntimeAttemptLedgerEntry({
          runId: options.runId,
          taskId: options.taskId,
          profile: "worker",
          attempt,
          maxAttempts: options.maxAttempts,
          prompt: attemptPrompt,
          timeoutMs: options.timeoutMs,
          maxTurns,
          outputPath: options.outputPath,
          result,
          validationReport,
          skipValidation: options.skipValidation,
          promptBudget: promptBudgetReport,
          maxTurnsReached,
          willRetry: shouldRetry,
          retryReason: shouldRetry ? retryReason : null,
          nextMaxTurns,
          startedAtMs,
          finishedAtMs,
        }),
      );
    }

    if (!shouldRetry) {
      return {
        result,
        validationReport,
      };
    }

    process.stderr.write(
      `Worker attempt ${attempt}/${options.maxAttempts} failed. Retrying: ${retryDetail}\n`,
    );

    if (Number.isFinite(nextMaxTurns)) {
      attemptCliArgs = bumpMaxTurnsCliArgs(attemptCliArgs, nextMaxTurns);
    }

    attempt += 1;
    attemptPrompt = buildRetryPrompt(options.prompt, {
      kind: "worker",
      attempt,
      reason: retryReason,
      detail: retryDetail,
    });
  }

  return {
    result: lastResult,
    validationReport: lastValidationReport,
  };
}

function normalizeMaxAttempts(rawValue) {
  const parsed = Number.parseInt(rawValue ?? "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 2;
}

function compactFailureDetail(text) {
  const normalized = `${text ?? ""}`.trim().replace(/\s+/g, " ");
  return normalized.length > 200 ? `${normalized.slice(0, 197)}...` : normalized;
}
