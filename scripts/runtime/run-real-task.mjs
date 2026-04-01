import { readFileSync } from "node:fs";
import process from "node:process";
import {
  buildRealTaskRunnerPreview,
  executeRealTaskRunner,
  renderRealTaskRunnerPreview,
  renderRealTaskRunnerSummary,
} from "./real-task-runner-lib.mjs";
import { resolveRepoPath } from "./orchestration-lib.mjs";

const rawArgs = process.argv.slice(2);
const separatorIndex = rawArgs.indexOf("--");
const args = separatorIndex === -1 ? rawArgs : rawArgs.slice(0, separatorIndex);
const forwardedArgs = separatorIndex === -1 ? [] : rawArgs.slice(separatorIndex + 1);

if (args.includes("--help")) {
  printUsageAndExit(0);
}

const requestText = resolveRequestText(args);
if (!requestText?.trim()) {
  printUsageAndExit(
    1,
    "Provide request text via --request, --input-file, or trailing text.",
  );
}

const previewOptions = {
  requestText,
  requestSourcePath: readFlagValue(args, "--input-file"),
  sessionInput: readJsonFile(readFlagValue(args, "--session-file")),
  sessionSourcePath: readFlagValue(args, "--session-file"),
  contextFiles: readFlagValues(args, "--context-file"),
  approachText:
    readFlagValue(args, "--approach") ?? readOptionalTextFile(readFlagValue(args, "--approach-file")),
  approachSourcePath: readFlagValue(args, "--approach-file"),
  filesChangedText: readOptionalTextFile(readFlagValue(args, "--files-changed-file")),
  filesChangedSourcePath: readFlagValue(args, "--files-changed-file"),
  routeId: readFlagValue(args, "--route"),
  classicCaseId: readFlagValue(args, "--classic-case"),
  noAutoRoute: args.includes("--no-auto-route"),
  pluginDirs: readFlagValues(args, "--plugin-dir"),
  taskId: readFlagValue(args, "--task-id"),
  outputDir: readFlagValue(args, "--output-dir"),
  structuredVerifier:
    args.includes("--no-structured-verifier") ? false : true,
  workerMaxAttempts: parseOptionalInteger(
    readFlagValue(args, "--worker-max-attempts"),
    "--worker-max-attempts",
  ),
  verifierMaxAttempts: parseOptionalInteger(
    readFlagValue(args, "--verifier-max-attempts"),
    "--verifier-max-attempts",
  ),
  workerTimeoutMs: parseOptionalInteger(
    readFlagValue(args, "--worker-timeout-ms"),
    "--worker-timeout-ms",
  ),
  verifierTimeoutMs: parseOptionalInteger(
    readFlagValue(args, "--verifier-timeout-ms"),
    "--verifier-timeout-ms",
  ),
  forwardedArgs,
};

const asJson = args.includes("--json");

if (args.includes("--dry-run")) {
  const preview = buildRealTaskRunnerPreview(previewOptions);
  process.stdout.write(
    asJson
      ? `${JSON.stringify(preview, null, 2)}\n`
      : renderRealTaskRunnerPreview(preview),
  );
  process.exit(0);
}

process.stderr.write("Preparing real-task artifact pack...\n");
const execution = executeRealTaskRunner(previewOptions);
process.stdout.write(
  asJson
    ? `${JSON.stringify(execution.summary, null, 2)}\n`
    : renderRealTaskRunnerSummary(execution.summary),
);
process.exit(execution.exitCode);

function resolveRequestText(argv) {
  const requestFromFlag = readFlagValue(argv, "--request");
  if (requestFromFlag) {
    return requestFromFlag;
  }

  const trailingText = readRemainingText(argv);
  if (trailingText) {
    return trailingText;
  }

  const inputFile = readFlagValue(argv, "--input-file");
  if (inputFile) {
    return readFileSync(resolveRepoPath(inputFile), "utf8").trim();
  }

  return "";
}

function readRemainingText(argv) {
  const flagsWithValues = new Set([
    "--request",
    "--input-file",
    "--session-file",
    "--context-file",
    "--approach",
    "--approach-file",
    "--files-changed-file",
    "--route",
    "--classic-case",
    "--plugin-dir",
    "--task-id",
    "--output-dir",
    "--worker-max-attempts",
    "--verifier-max-attempts",
    "--worker-timeout-ms",
    "--verifier-timeout-ms",
  ]);
  const values = [];

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (flagsWithValues.has(value) && index < argv.length - 1) {
      index += 1;
      continue;
    }

    if (value.startsWith("--")) {
      continue;
    }

    values.push(value);
  }

  return values.join(" ").trim();
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
      printUsageAndExit(1, `Missing value for ${flagName}.`);
    }

    values.push(argv[index + 1]);
    index += 1;
  }

  return values;
}

function readJsonFile(filePath) {
  if (!filePath) {
    return {};
  }

  return JSON.parse(readFileSync(resolveRepoPath(filePath), "utf8"));
}

function readOptionalTextFile(filePath) {
  if (!filePath) {
    return "";
  }

  return readFileSync(resolveRepoPath(filePath), "utf8").trim();
}

function parseOptionalInteger(value, flagName) {
  if (value == null) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    printUsageAndExit(1, `Invalid value for ${flagName}: ${value}`);
  }

  return parsed;
}

function printUsageAndExit(exitCode, message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }

  process.stderr.write(
    "Usage: node scripts/runtime/run-real-task.mjs [--request <text> | --input-file <path> | trailing text] [--session-file <path>] [--context-file <path>] [--approach <text> | --approach-file <path>] [--files-changed-file <path>] [--route <id>] [--classic-case <id>] [--plugin-dir <path>] [--task-id <id>] [--output-dir <path>] [--no-structured-verifier] [--worker-max-attempts <n>] [--verifier-max-attempts <n>] [--worker-timeout-ms <n>] [--verifier-timeout-ms <n>] [--no-auto-route] [--dry-run] [--json] [-- <runtime args...>]\n",
  );
  process.exit(exitCode);
}
