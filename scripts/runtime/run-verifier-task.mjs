import { existsSync, readFileSync, writeFileSync } from "node:fs";
import process from "node:process";
import {
  buildRetryPrompt,
  buildTaskProfilePreview,
  buildStructuredVerifierPrompt,
  buildVerifierPrompt,
  bumpMaxTurnsCliArgs,
  getMaxTurnsFromCliArgs,
  normalizeWorkerOutputForVerification,
  parseVerifierOutput,
  renderDeterministicPreflight,
  renderStructuredVerifierMarkdown,
  resolveRepoPath,
  validateStructuredVerifierReport,
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

const originalTaskFilePath = readFlagValue(args, "--original-task-file");
const originalTask = getRequiredText(args, "--original-task", "--original-task-file");
const taskId = deriveRuntimeTaskId({
  explicitTaskId: readFlagValue(args, "--task-id"),
  sourcePath: readFlagValue(args, "--plan-path") ?? originalTaskFilePath,
  fallback: "verifier-inline-task",
});
const workerOutputPath = readFlagValue(args, "--worker-output-file");
if (!workerOutputPath) {
  printUsageAndExit("Missing --worker-output-file.");
}

const workerOutput = normalizeWorkerOutputForVerification(
  readFileSync(resolveRepoPath(workerOutputPath), "utf8"),
);
const filesChanged = getFilesChanged(args);
const approach = getOptionalText(args, "--approach", "--approach-file");
const planPath = readFlagValue(args, "--plan-path");
const outputPath = readFlagValue(args, "--output");
const attemptLedgerPath = readFlagValue(args, "--attempt-ledger-file");
const structuredVerifier = args.includes("--structured-verifier");
const structuredOutputPath = readFlagValue(args, "--structured-output-file");
const format = normalizeFormat(args);
const timeoutMs = Number.parseInt(readFlagValue(args, "--timeout-ms") ?? "", 10);
const maxAttempts = normalizeMaxAttempts(readFlagValue(args, "--max-attempts"));
const nowMarkdown = readOptionalFile(getStateFilePath(args, "--now-file", "runtime-state/NOW.md"));
const intentMarkdown = readOptionalFile(getStateFilePath(args, "--intent-file", "runtime-state/INTENT.md"));

const preflight = validateWorkerOutput(workerOutput);
const preflightSummary = renderDeterministicPreflight(preflight);

if (args.includes("--local-only")) {
  writeOutput(
    {
      mode: "local-only",
      preflight,
      preflightSummary,
      taskId,
      structuredVerifier,
      attemptLedgerPath: attemptLedgerPath ? resolveRepoPath(attemptLedgerPath) : null,
      structuredOutputPath: structuredOutputPath ? resolveRepoPath(structuredOutputPath) : null,
    },
    format,
    outputPath,
    preflight.ok ? 0 : 1,
  );
}

if (!preflight.ok && !args.includes("--allow-invalid-worker-output")) {
  writeOutput(
    {
      mode: "preflight-failed",
      preflight,
      preflightSummary,
    },
    format,
    outputPath,
    1,
  );
}

const prompt = structuredVerifier
  ? buildStructuredVerifierPrompt({
      originalTask,
      workerOutput,
      filesChanged,
      approach,
      planPath,
      nowMarkdown,
      intentMarkdown,
      preflightReport: preflightSummary,
    })
  : buildVerifierPrompt({
      originalTask,
      workerOutput,
      filesChanged,
      approach,
      planPath,
      nowMarkdown,
      intentMarkdown,
      preflightReport: preflightSummary,
    });

const preview = buildTaskProfilePreview("verifier", {
  pluginDirs: readFlagValues(args, "--plugin-dir"),
  allPlugins: args.includes("--all-plugins"),
  includePartnerBuilt: args.includes("--include-partner-built"),
  forwardedArgs: ensureHeadlessTextArgs(forwardedArgs),
});
const initialBudgetReport = buildPromptBudgetReport({
  profile: "verifier",
  prompt,
  cliArgs: preview.invocation.cliArgs,
  structuredVerifier,
  segments: [
    { label: "Original task", content: originalTask },
    { label: "Worker output", content: workerOutput },
    { label: "Files changed", content: filesChanged.join("\n") },
    { label: "Approach", content: approach },
    { label: "Intent", content: intentMarkdown },
    { label: "NOW", content: nowMarkdown },
    { label: "Preflight", content: preflightSummary },
  ],
});
const promptBudgetGuardrail = applyPromptBudgetGuardrails(preview.invocation.cliArgs, initialBudgetReport, {
  allowAutoBump: !forwardedArgs.includes("--max-turns"),
});

if (args.includes("--dry-run")) {
  writeOutput(
    {
      ...preview,
      invocation: {
        ...preview.invocation,
        cliArgs: promptBudgetGuardrail.cliArgs,
      },
      prompt,
      preflight,
      taskId,
      structuredVerifier,
      attemptLedgerPath: attemptLedgerPath ? resolveRepoPath(attemptLedgerPath) : null,
      structuredOutputPath: structuredOutputPath ? resolveRepoPath(structuredOutputPath) : null,
      promptBudgetReport: initialBudgetReport,
      promptBudgetGuardrail,
    },
    format,
    outputPath,
    0,
  );
}

const resolvedOutputPath = outputPath ? resolveRepoPath(outputPath) : null;
const resolvedAttemptLedgerPath = attemptLedgerPath ? resolveRepoPath(attemptLedgerPath) : null;
const resolvedStructuredOutputPath = structuredOutputPath ? resolveRepoPath(structuredOutputPath) : null;
const runId = resolvedAttemptLedgerPath ? createRuntimeRunId("verifier", taskId) : null;
const execution = runVerifierWithRetries({
  cliArgs: promptBudgetGuardrail.cliArgs,
  prompt,
  timeoutMs,
  maxAttempts,
  skipValidation: args.includes("--skip-validation"),
  runId,
  taskId,
  outputPath: resolvedOutputPath,
  structuredOutputPath: resolvedStructuredOutputPath,
  structuredVerifier,
  promptBudgetReport: initialBudgetReport,
  promptBudgetGuardrailReason: promptBudgetGuardrail.reason,
  recordAttempt: resolvedAttemptLedgerPath
    ? (entry) => appendRuntimeAttemptLedgerEntry(resolvedAttemptLedgerPath, entry)
    : null,
});
const result = execution.result;
const validationReport = execution.validationReport;

if (result.stderr) {
  process.stderr.write(result.stderr);
}

if ((result.status ?? 1) !== 0) {
  if (result.stdout) {
    process.stdout.write(result.stdout);
  }
  process.exit(result.status ?? 1);
}

if (!(result.stdout ?? "").trim()) {
  process.stderr.write("Runtime returned empty stdout for verifier output.\n");
  process.exit(2);
}

if (!args.includes("--skip-validation")) {
  if (!validationReport?.ok) {
    process.stderr.write(`\nVerifier output failed wrapper validation.\n`);
    if (structuredVerifier) {
      if (validationReport?.parseError) {
        process.stderr.write(`- JSON parse error: ${validationReport.parseError}\n`);
      }
      if (!validationReport?.parseError && !validationReport?.schemaVersion) {
        process.stderr.write("- Missing or invalid schemaVersion.\n");
      }
      if (!validationReport?.verdict) {
        process.stderr.write("- Missing or invalid verdict.\n");
      }
      if (!validationReport?.parseError && !validationReport?.hasAdversarialProbe) {
        process.stderr.write("- Missing or invalid adversarial probe.\n");
      }
      for (const invalidField of validationReport?.invalidFields ?? []) {
        process.stderr.write(`- Invalid field: ${invalidField}\n`);
      }
    } else {
      if (!validationReport?.verdict) {
        process.stderr.write("- Missing final VERDICT line.\n");
      }
      if (!validationReport?.hasAdversarialProbe) {
        process.stderr.write("- Missing adversarial probe.\n");
      }
    }
    for (const missingField of validationReport?.missingFields ?? []) {
      process.stderr.write(`- Missing field: ${missingField}\n`);
    }
    if (result.stdout) {
      process.stdout.write(result.stdout);
    }
    process.exit(2);
  }
}

const renderedOutput =
  structuredVerifier && validationReport?.report
    ? renderStructuredVerifierMarkdown(validationReport.report)
    : result.stdout ?? "";

if (resolvedOutputPath) {
  writeRuntimeOutputFile(resolvedOutputPath, renderedOutput);
}

if (structuredVerifier && resolvedStructuredOutputPath && validationReport?.raw) {
  writeRuntimeOutputFile(resolvedStructuredOutputPath, `${validationReport.raw.trim()}\n`);
}

if (renderedOutput) {
  process.stdout.write(renderedOutput);
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

function getFilesChanged(argv) {
  const inlineValues = readFlagValues(argv, "--file-changed");
  const fileListPath = readFlagValue(argv, "--files-changed-file");
  const fromFile = fileListPath
    ? readFileSync(resolveRepoPath(fileListPath), "utf8")
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
    : [];

  return [...inlineValues, ...fromFile];
}

function getRequiredText(argv, inlineFlag, fileFlag) {
  const value = getOptionalText(argv, inlineFlag, fileFlag);
  if (value) {
    return value;
  }
  printUsageAndExit(`Missing ${inlineFlag} or ${fileFlag}.`);
}

function getOptionalText(argv, inlineFlag, fileFlag) {
  const inlineValue = readFlagValue(argv, inlineFlag);
  if (inlineValue) {
    return inlineValue;
  }
  const fileValue = readFlagValue(argv, fileFlag);
  if (fileValue) {
    return readFileSync(resolveRepoPath(fileValue), "utf8").trim();
  }
  return "";
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
      printUsageAndExit(`Missing value for ${flagName}.`);
    }
    values.push(argv[index + 1]);
    index += 1;
  }
  return values;
}

function writeOutput(payload, format, outputPath, exitCode) {
  const serialized =
    format === "text"
      ? `${payload.preflightSummary ?? payload.prompt ?? JSON.stringify(payload, null, 2)}\n`
      : `${JSON.stringify(payload, null, 2)}\n`;

  if (outputPath) {
    writeFileSync(resolveRepoPath(outputPath), serialized, "utf8");
  } else {
    process.stdout.write(serialized);
  }

  process.exit(exitCode);
}

function printUsageAndExit(message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }
  process.stderr.write(
    "Usage: node scripts/runtime/run-verifier-task.mjs (--original-task <text> | --original-task-file <file>) --worker-output-file <file> [--task-id <id>] [--file-changed <path>] [--files-changed-file <file>] [--approach <text> | --approach-file <file>] [--plan-path <path>] [--local-only] [--dry-run] [--json] [--now-file <file>] [--intent-file <file>] [--output <file>] [--attempt-ledger-file <file>] [--structured-verifier] [--structured-output-file <file>] [--timeout-ms <n>] [--max-attempts <n>] [--allow-invalid-worker-output] [--skip-validation] [--plugin-dir <path>] [--all-plugins] [--include-partner-built] [-- <runtime args...>]\n",
  );
  process.exit(1);
}

function runVerifierWithRetries(options) {
  let attempt = 1;
  let attemptPrompt = options.prompt;
  let attemptCliArgs = [...options.cliArgs];
  let lastResult = null;
  let lastValidationReport = null;

  while (attempt <= options.maxAttempts) {
    const promptBudgetReport = buildPromptBudgetReport({
      profile: "verifier",
      prompt: attemptPrompt,
      cliArgs: attemptCliArgs,
      structuredVerifier: options.structuredVerifier,
      segments: [{ label: "Verifier prompt", content: attemptPrompt }],
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
        ? options.structuredVerifier
          ? validateStructuredVerifierReport(stdout)
          : parseVerifierOutput(stdout)
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
            ? buildVerifierFailureDetail(validationReport)
            : "";
    const retryReason =
      status !== 0 && maxTurnsReached
        ? "previous attempt reached max turns"
        : !hasContent
          ? "previous attempt returned empty stdout"
          : "previous attempt violated the verifier contract";

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
          profile: "verifier",
          attempt,
          maxAttempts: options.maxAttempts,
          prompt: attemptPrompt,
          timeoutMs: options.timeoutMs,
          maxTurns,
          outputPath: options.outputPath,
          structuredOutputPath: options.structuredOutputPath,
          structuredVerifier: options.structuredVerifier,
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
      `Verifier attempt ${attempt}/${options.maxAttempts} failed. Retrying: ${retryDetail}\n`,
    );

    if (Number.isFinite(nextMaxTurns)) {
      attemptCliArgs = bumpMaxTurnsCliArgs(attemptCliArgs, nextMaxTurns);
    }

    attempt += 1;
    attemptPrompt = buildRetryPrompt(options.prompt, {
      kind: "verifier",
      structuredOutput: options.structuredVerifier,
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
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 3;
}

function buildVerifierFailureDetail(report) {
  const parts = [];
  if (report.parseError) {
    parts.push(`json parse error: ${report.parseError}`);
  }
  if (!report.verdict) {
    parts.push("missing verdict");
  }
  if (!report.hasAdversarialProbe) {
    parts.push("missing adversarial probe");
  }
  if (report.missingFields.length > 0) {
    parts.push(`missing fields: ${report.missingFields.join(", ")}`);
  }
  if (report.invalidFields?.length > 0) {
    parts.push(`invalid fields: ${report.invalidFields.join(", ")}`);
  }

  return parts.join("; ") || "verifier output failed wrapper validation";
}

function compactFailureDetail(text) {
  const normalized = `${text ?? ""}`.trim().replace(/\s+/g, " ");
  return normalized.length > 240 ? `${normalized.slice(0, 237)}...` : normalized;
}
