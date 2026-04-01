import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import process from "node:process";
import {
  buildIntentPayload,
  buildSessionStatePayload,
  parseVerifierOutput,
  resolveRepoPath,
  validateStructuredVerifierReport,
} from "./orchestration-lib.mjs";
import { routeRequest } from "./request-router-lib.mjs";
import { repoRoot } from "./runtime-report-lib.mjs";
import {
  buildRuntimeAttemptScorecard,
  deriveRuntimeTaskId,
  loadRuntimeAttemptLedger,
  renderRuntimeAttemptScorecardText,
} from "./runtime-attempt-ledger-lib.mjs";

export const REAL_TASK_RUNNER_SCHEMA_VERSION = "real-task-runner-v1";
export const DEFAULT_REAL_TASK_OUTPUT_ROOT = path.join(
  "runtime-state",
  "real-task-runs",
);

const WORKER_SCRIPT_PATH = path.join("scripts", "runtime", "run-worker-task.mjs");
const VERIFIER_SCRIPT_PATH = path.join(
  "scripts",
  "runtime",
  "run-verifier-task.mjs",
);

export function buildRealTaskRunnerPreview(options = {}) {
  const requestText = `${options.requestText ?? ""}`.trim();
  if (!requestText) {
    throw new Error("Real-task runner requires non-empty request text.");
  }

  const routePlan = routeRequest(requestText, {
    routeId: options.routeId,
    classicCaseId: options.classicCaseId,
    profile: options.routeProfile,
    pluginDirs: options.pluginDirs ?? [],
    noAutoRoute: options.noAutoRoute === true,
  });
  const taskId = deriveRuntimeTaskId({
    explicitTaskId: options.taskId,
    sourcePath: options.requestSourcePath,
    fallback: `${routePlan.classicCaseId ?? routePlan.routeId}-task`,
  });
  const outputDir = resolveOutputDir(options.outputDir, taskId);
  const sessionInput = options.sessionInput ?? {};
  const intentPayload = buildIntentPayload(requestText, {
    currentState: options.currentState,
    nextStep: options.nextStep,
  });
  const nowPayload = buildSessionStatePayload(sessionInput);
  const routeGuidanceMarkdown = buildRouteGuidanceMarkdown(routePlan);
  const approachText = `${options.approachText ?? ""}`.trim();
  const filesChangedText = normalizeMultilineText(options.filesChangedText);
  const artifacts = buildArtifactManifest(outputDir, {
    structuredVerifier: options.structuredVerifier !== false,
    contextFiles: options.contextFiles ?? [],
    requestSourcePath: options.requestSourcePath ?? null,
    sessionSourcePath: options.sessionSourcePath ?? null,
    approachSourcePath: options.approachSourcePath ?? null,
    filesChangedSourcePath: options.filesChangedSourcePath ?? null,
  });

  const copiedContexts = [
    {
      label: "Context: Route guidance",
      sourcePath: null,
      materializedPath: artifacts.routeGuidancePath,
    },
    ...artifacts.contextFiles.map((contextFile) => ({
      label: contextFile.label,
      sourcePath: contextFile.sourcePath,
      materializedPath: contextFile.materializedPath,
    })),
  ];

  const workerCommand = buildWorkerCommand({
    taskId,
    artifacts,
    copiedContexts,
    pluginDirs: routePlan.pluginDirs,
    workerMaxAttempts: options.workerMaxAttempts,
    workerTimeoutMs: options.workerTimeoutMs,
    forwardedArgs: options.forwardedArgs ?? [],
  });
  const verifierPreflightCommand = buildVerifierCommand({
    taskId,
    artifacts,
    pluginDirs: routePlan.pluginDirs,
    structuredVerifier: options.structuredVerifier !== false,
    hasApproach: Boolean(approachText),
    hasFilesChanged: Boolean(filesChangedText),
    verifierMaxAttempts: null,
    verifierTimeoutMs: null,
    forwardedArgs: [],
    localOnly: true,
  });
  const verifierCommand = buildVerifierCommand({
    taskId,
    artifacts,
    pluginDirs: routePlan.pluginDirs,
    structuredVerifier: options.structuredVerifier !== false,
    hasApproach: Boolean(approachText),
    hasFilesChanged: Boolean(filesChangedText),
    verifierMaxAttempts: options.verifierMaxAttempts,
    verifierTimeoutMs: options.verifierTimeoutMs,
    forwardedArgs: options.forwardedArgs ?? [],
    localOnly: false,
  });

  return {
    schemaVersion: REAL_TASK_RUNNER_SCHEMA_VERSION,
    generatedAt: new Date().toISOString(),
    mode: "preview",
    taskId,
    requestText,
    requestSourcePath: options.requestSourcePath ?? null,
    sessionSourcePath: options.sessionSourcePath ?? null,
    routePlan,
    structuredVerifier: options.structuredVerifier !== false,
    outputDir,
    generatedState: {
      intentMarkdown: intentPayload.intentMarkdown,
      intentCompactMarkdown: intentPayload.compactSummary,
      nowMarkdown: nowPayload.markdown,
      routeGuidanceMarkdown,
      approachText: approachText || null,
      filesChangedText: filesChangedText || null,
    },
    artifacts,
    commands: {
      worker: workerCommand,
      verifierPreflight: verifierPreflightCommand,
      verifier: verifierCommand,
    },
  };
}

export function materializeRealTaskRunnerInputs(preview) {
  mkdirSync(preview.outputDir, { recursive: true });
  mkdirSync(preview.artifacts.contextDir, { recursive: true });

  writeUtf8File(preview.artifacts.rawRequestPath, `${preview.requestText.trim()}\n`);
  writeUtf8File(preview.artifacts.taskPath, `${preview.requestText.trim()}\n`);
  writeJsonFile(preview.artifacts.routePlanPath, preview.routePlan);
  writeUtf8File(
    preview.artifacts.routeGuidancePath,
    `${preview.generatedState.routeGuidanceMarkdown.trim()}\n`,
  );
  writeUtf8File(
    preview.artifacts.intentPath,
    `${preview.generatedState.intentMarkdown.trim()}\n`,
  );
  writeUtf8File(
    preview.artifacts.intentCompactPath,
    `${preview.generatedState.intentCompactMarkdown.trim()}\n`,
  );
  writeUtf8File(preview.artifacts.nowPath, `${preview.generatedState.nowMarkdown.trim()}\n`);
  writeJsonFile(preview.artifacts.runPlanPath, preview);

  if (preview.sessionSourcePath) {
    copyTextArtifact(preview.sessionSourcePath, preview.artifacts.sessionInputCopyPath);
  }

  for (const contextFile of preview.artifacts.contextFiles) {
    copyTextArtifact(contextFile.sourcePath, contextFile.materializedPath);
  }

  if (preview.generatedState.approachText) {
    writeUtf8File(
      preview.artifacts.approachPath,
      `${preview.generatedState.approachText.trim()}\n`,
    );
  }

  if (preview.generatedState.filesChangedText) {
    writeUtf8File(
      preview.artifacts.filesChangedPath,
      `${preview.generatedState.filesChangedText.trim()}\n`,
    );
  }

  return preview;
}

export function executeRealTaskRunner(options = {}) {
  const preview = buildRealTaskRunnerPreview(options);
  materializeRealTaskRunnerInputs(preview);

  const summary = {
    ...preview,
    mode: "executed",
    stage: "prepared",
    results: {
      worker: null,
      verifierPreflight: null,
      verifier: null,
    },
    scorecard: null,
  };

  writeSummary(summary);

  const workerResult = runNodeCommand(preview.commands.worker);
  summary.results.worker = summarizeCommandResult(preview.commands.worker, workerResult);
  if (workerResult.status !== 0) {
    summary.stage = "worker_failed";
    finalizeSummary(summary);
    return {
      ok: false,
      exitCode: workerResult.status ?? 1,
      summary,
    };
  }

  const verifierPreflightResult = runNodeCommand(preview.commands.verifierPreflight);
  summary.results.verifierPreflight = summarizeCommandResult(
    preview.commands.verifierPreflight,
    verifierPreflightResult,
  );
  summary.results.verifierPreflight.payload = readOptionalJson(
    preview.artifacts.verifierPreflightPath,
  );
  if (verifierPreflightResult.status !== 0) {
    summary.stage = "verifier_preflight_failed";
    finalizeSummary(summary);
    return {
      ok: false,
      exitCode: verifierPreflightResult.status ?? 1,
      summary,
    };
  }

  const verifierResult = runNodeCommand(preview.commands.verifier);
  summary.results.verifier = summarizeCommandResult(preview.commands.verifier, verifierResult);
  if (verifierResult.status !== 0) {
    summary.stage = "verifier_failed";
    finalizeSummary(summary);
    return {
      ok: false,
      exitCode: verifierResult.status ?? 1,
      summary,
    };
  }

  const semanticGate = evaluateVerifierSemanticGate(preview);
  summary.results.verifier.semanticGate = semanticGate;
  if (!semanticGate.ok) {
    summary.stage = "verifier_rejected";
    finalizeSummary(summary);
    return {
      ok: false,
      exitCode: 2,
      summary,
    };
  }

  summary.stage = "completed";
  finalizeSummary(summary);
  return {
    ok: true,
    exitCode: 0,
    summary,
  };
}

export function renderRealTaskRunnerPreview(preview) {
  const lines = [];
  lines.push(`Task: ${preview.taskId}`);
  lines.push(`Mode: ${preview.mode}`);
  lines.push(`Route: ${preview.routePlan.routeId}`);
  if (preview.routePlan.classicCaseId) {
    lines.push(`Classic case: ${preview.routePlan.classicCaseId}`);
  }
  lines.push(`Structured verifier: ${preview.structuredVerifier}`);
  lines.push(`Output dir: ${preview.outputDir}`);
  lines.push("Plugin dirs:");
  for (const pluginDir of preview.routePlan.pluginDirs) {
    lines.push(`- ${pluginDir}`);
  }
  lines.push("Artifacts:");
  lines.push(`- task: ${preview.artifacts.taskPath}`);
  lines.push(`- intent: ${preview.artifacts.intentPath}`);
  lines.push(`- now: ${preview.artifacts.nowPath}`);
  lines.push(`- worker_output: ${preview.artifacts.workerOutputPath}`);
  lines.push(`- verifier_output: ${preview.artifacts.verifierOutputPath}`);
  if (preview.artifacts.verifierStructuredOutputPath) {
    lines.push(
      `- verifier_structured_output: ${preview.artifacts.verifierStructuredOutputPath}`,
    );
  }
  lines.push(`- attempt_ledger: ${preview.artifacts.attemptLedgerPath}`);
  lines.push("Commands:");
  lines.push(`- worker: ${preview.commands.worker.displayCommand}`);
  lines.push(
    `- verifier_preflight: ${preview.commands.verifierPreflight.displayCommand}`,
  );
  lines.push(`- verifier: ${preview.commands.verifier.displayCommand}`);

  return `${lines.join("\n")}\n`;
}

export function renderRealTaskRunnerSummary(summary) {
  const lines = [];
  lines.push(`Task: ${summary.taskId}`);
  lines.push(`Stage: ${summary.stage}`);
  lines.push(`Route: ${summary.routePlan.routeId}`);
  lines.push(`Output dir: ${summary.outputDir}`);
  lines.push(`Worker output: ${summary.artifacts.workerOutputPath}`);
  lines.push(`Verifier output: ${summary.artifacts.verifierOutputPath}`);
  lines.push(`Attempt ledger: ${summary.artifacts.attemptLedgerPath}`);
  lines.push(`Attempt scorecard: ${summary.artifacts.attemptScorecardTextPath}`);

  appendResultSummary(lines, "Worker", summary.results.worker);
  appendResultSummary(lines, "Verifier preflight", summary.results.verifierPreflight);
  appendResultSummary(lines, "Verifier", summary.results.verifier);

  return `${lines.join("\n")}\n`;
}

function buildArtifactManifest(outputDir, options) {
  const normalizedContextFiles = [...(options.contextFiles ?? [])].map((contextFile, index) => {
    const sourcePath = resolveRepoPath(contextFile);
    const fileName = path.basename(sourcePath);
    const prefix = String(index + 1).padStart(2, "0");

    return {
      index,
      label: `Context: ${path.basename(fileName, path.extname(fileName))}`,
      sourcePath,
      materializedPath: path.join(outputDir, "contexts", `${prefix}-${fileName}`),
    };
  });

  return {
    outputDir,
    requestSourcePath: options.requestSourcePath,
    sessionSourcePath: options.sessionSourcePath,
    approachSourcePath: options.approachSourcePath,
    filesChangedSourcePath: options.filesChangedSourcePath,
    rawRequestPath: path.join(outputDir, "raw-request.txt"),
    taskPath: path.join(outputDir, "task.md"),
    routePlanPath: path.join(outputDir, "route-plan.json"),
    routeGuidancePath: path.join(outputDir, "contexts", "00-route-guidance.md"),
    intentPath: path.join(outputDir, "INTENT.md"),
    intentCompactPath: path.join(outputDir, "INTENT-COMPACT.md"),
    nowPath: path.join(outputDir, "NOW.md"),
    sessionInputCopyPath: path.join(outputDir, "session-input.json"),
    approachPath: path.join(outputDir, "approach.md"),
    filesChangedPath: path.join(outputDir, "files-changed.txt"),
    contextDir: path.join(outputDir, "contexts"),
    contextFiles: normalizedContextFiles,
    workerOutputPath: path.join(outputDir, "worker-output.md"),
    verifierPreflightPath: path.join(outputDir, "verifier-preflight.json"),
    verifierOutputPath: path.join(outputDir, "verifier-output.md"),
    verifierStructuredOutputPath: options.structuredVerifier
      ? path.join(outputDir, "verifier-output.json")
      : null,
    attemptLedgerPath: path.join(outputDir, "runtime-attempts.ndjson"),
    attemptScorecardJsonPath: path.join(outputDir, "runtime-attempt-scorecard.json"),
    attemptScorecardTextPath: path.join(outputDir, "runtime-attempt-scorecard.txt"),
    runPlanPath: path.join(outputDir, "run-plan.json"),
    runSummaryPath: path.join(outputDir, "run-summary.json"),
  };
}

function buildWorkerCommand(options) {
  const args = [
    path.join(repoRoot, WORKER_SCRIPT_PATH),
    "--task-file",
    options.artifacts.taskPath,
    "--task-id",
    options.taskId,
    "--intent-file",
    options.artifacts.intentPath,
    "--now-file",
    options.artifacts.nowPath,
    "--attempt-ledger-file",
    options.artifacts.attemptLedgerPath,
    "--output",
    options.artifacts.workerOutputPath,
  ];

  for (const contextItem of options.copiedContexts) {
    args.push("--context-file", contextItem.materializedPath);
  }

  for (const pluginDir of options.pluginDirs) {
    args.push("--plugin-dir", pluginDir);
  }

  if (Number.isFinite(options.workerMaxAttempts)) {
    args.push("--max-attempts", String(options.workerMaxAttempts));
  }

  if (Number.isFinite(options.workerTimeoutMs)) {
    args.push("--timeout-ms", String(options.workerTimeoutMs));
  }

  if ((options.forwardedArgs ?? []).length > 0) {
    args.push("--", ...options.forwardedArgs);
  }

  return buildNodeCommand(args);
}

function buildVerifierCommand(options) {
  const args = [
    path.join(repoRoot, VERIFIER_SCRIPT_PATH),
    "--original-task-file",
    options.artifacts.taskPath,
    "--task-id",
    options.taskId,
    "--worker-output-file",
    options.artifacts.workerOutputPath,
    "--intent-file",
    options.artifacts.intentPath,
    "--now-file",
    options.artifacts.nowPath,
  ];

  if (options.hasFilesChanged) {
    args.push("--files-changed-file", options.artifacts.filesChangedPath);
  }

  if (options.hasApproach) {
    args.push("--approach-file", options.artifacts.approachPath);
  }

  for (const pluginDir of options.pluginDirs) {
    args.push("--plugin-dir", pluginDir);
  }

  if (options.localOnly) {
    args.push(
      "--local-only",
      "--json",
      "--output",
      options.artifacts.verifierPreflightPath,
    );
  } else {
    args.push(
      "--attempt-ledger-file",
      options.artifacts.attemptLedgerPath,
      "--output",
      options.artifacts.verifierOutputPath,
    );

    if (options.structuredVerifier) {
      args.push("--structured-verifier");
      if (options.artifacts.verifierStructuredOutputPath) {
        args.push(
          "--structured-output-file",
          options.artifacts.verifierStructuredOutputPath,
        );
      }
    }

    if (Number.isFinite(options.verifierMaxAttempts)) {
      args.push("--max-attempts", String(options.verifierMaxAttempts));
    }

    if (Number.isFinite(options.verifierTimeoutMs)) {
      args.push("--timeout-ms", String(options.verifierTimeoutMs));
    }

    if ((options.forwardedArgs ?? []).length > 0) {
      args.push("--", ...options.forwardedArgs);
    }
  }

  return buildNodeCommand(args);
}

function buildNodeCommand(args) {
  return {
    command: process.execPath,
    args,
    displayCommand: ["node", ...args].join(" "),
  };
}

function buildRouteGuidanceMarkdown(routePlan) {
  const lines = ["# Route Guidance", ""];
  lines.push("## Matched Route");
  lines.push(`- Route: ${routePlan.routeId}`);
  if (routePlan.classicCaseId) {
    lines.push(`- Classic case: ${routePlan.classicCaseId}`);
  }
  lines.push(`- Confidence: ${routePlan.confidence}`);
  lines.push("");
  lines.push("## Native Workflow");
  for (const workflowItem of routePlan.nativeWorkflow) {
    lines.push(`- ${workflowItem}`);
  }
  lines.push("");
  lines.push("## Routing Notes");
  for (const note of routePlan.notes) {
    lines.push(`- ${note}`);
  }
  lines.push("");
  lines.push("## Execution Shape");
  lines.push("- Run the main answer through the worker wrapper.");
  lines.push("- Run verifier preflight before the final verifier pass.");
  lines.push("- Fail closed if worker output or verifier review violates the wrapper contract.");

  return `${lines.join("\n").trimEnd()}\n`;
}

function resolveOutputDir(explicitOutputDir, taskId) {
  if (explicitOutputDir) {
    return resolveRepoPath(explicitOutputDir);
  }

  return resolveRepoPath(
    path.join(DEFAULT_REAL_TASK_OUTPUT_ROOT, taskId, buildTimestampStamp()),
  );
}

function buildTimestampStamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function copyTextArtifact(sourcePath, destinationPath) {
  const resolvedSourcePath = resolveRepoPath(sourcePath);
  const content = readFileSync(resolvedSourcePath, "utf8");
  writeUtf8File(destinationPath, content);
}

function writeUtf8File(filePath, content) {
  mkdirSync(path.dirname(filePath), { recursive: true });
  writeFileSync(filePath, content, "utf8");
}

function writeJsonFile(filePath, payload) {
  writeUtf8File(filePath, `${JSON.stringify(payload, null, 2)}\n`);
}

function runNodeCommand(command) {
  return spawnSync(command.command, command.args, {
    cwd: repoRoot,
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
  });
}

function summarizeCommandResult(command, result) {
  return {
    command: command.displayCommand,
    exitCode: result.status ?? null,
    signal: result.signal ?? null,
    ok: result.status === 0,
    stdoutPreview: firstNonEmptyLine(result.stdout),
    stderrPreview: firstNonEmptyLine(result.stderr),
  };
}

function finalizeSummary(summary) {
  const scorecard = buildAndWriteScorecard(summary.artifacts);
  summary.scorecard = scorecard;
  writeSummary(summary);
}

function writeSummary(summary) {
  writeJsonFile(summary.artifacts.runSummaryPath, summary);
}

function buildAndWriteScorecard(artifacts) {
  const entries = loadRuntimeAttemptLedger(artifacts.attemptLedgerPath);
  const scorecard = buildRuntimeAttemptScorecard(entries, {
    inputFile: artifacts.attemptLedgerPath,
  });

  writeJsonFile(artifacts.attemptScorecardJsonPath, scorecard);
  writeUtf8File(
    artifacts.attemptScorecardTextPath,
    renderRuntimeAttemptScorecardText(scorecard),
  );

  return scorecard;
}

function readOptionalJson(filePath) {
  if (!filePath || !existsSync(filePath)) {
    return null;
  }

  return JSON.parse(readFileSync(filePath, "utf8"));
}

function firstNonEmptyLine(text) {
  return `${text ?? ""}`
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean) ?? null;
}

function appendResultSummary(lines, label, result) {
  if (!result) {
    return;
  }

  lines.push(`${label}: ${result.ok ? "OK" : "FAIL"} (exit=${result.exitCode})`);
  if (result.stderrPreview) {
    lines.push(`- ${label.toLowerCase()} stderr: ${result.stderrPreview}`);
  } else if (result.stdoutPreview) {
    lines.push(`- ${label.toLowerCase()} stdout: ${result.stdoutPreview}`);
  }
  if (result.semanticGate) {
    lines.push(
      `- ${label.toLowerCase()} semantic gate: ${result.semanticGate.ok ? "PASS" : "FAIL"} (${result.semanticGate.detail})`,
    );
  }
}

function normalizeMultilineText(text) {
  const normalized = `${text ?? ""}`.trim();
  return normalized || "";
}

function evaluateVerifierSemanticGate(preview) {
  if (preview.structuredVerifier !== false) {
    const report = validateStructuredVerifierReport(
      readOptionalText(preview.artifacts.verifierStructuredOutputPath),
    );

    if (!report.ok) {
      return {
        ok: false,
        verdict: report.verdict ?? null,
        detail: report.parseError
          ? `structured verifier artifact is invalid: ${report.parseError}`
          : "structured verifier artifact failed schema validation",
      };
    }

    return {
      ok: report.verdict === "PASS",
      verdict: report.verdict ?? null,
      detail: `structured verdict=${report.verdict ?? "unknown"}`,
    };
  }

  const report = parseVerifierOutput(readOptionalText(preview.artifacts.verifierOutputPath));
  if (!report.ok) {
    return {
      ok: false,
      verdict: report.verdict ?? null,
      detail: "markdown verifier artifact failed wrapper validation",
    };
  }

  return {
    ok: report.verdict === "PASS",
    verdict: report.verdict ?? null,
    detail: `markdown verdict=${report.verdict ?? "unknown"}`,
  };
}

function readOptionalText(filePath) {
  if (!filePath || !existsSync(filePath)) {
    return "";
  }

  return readFileSync(filePath, "utf8");
}
