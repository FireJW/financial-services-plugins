import { spawnSync } from "node:child_process";
import process from "node:process";
import { buildRuntimeHostReliabilitySuitePreview } from "./runtime-host-reliability-suite-lib.mjs";

const rawArgs = process.argv.slice(2);
const separatorIndex = rawArgs.indexOf("--");
const args = separatorIndex === -1 ? rawArgs : rawArgs.slice(0, separatorIndex);
const forwardedArgs = separatorIndex === -1 ? [] : rawArgs.slice(separatorIndex + 1);

if (args.includes("--help")) {
  printUsageAndExit(0);
}

const preview = buildRuntimeHostReliabilitySuitePreview({ forwardedArgs });

if (args.includes("--list")) {
  process.stdout.write(`${preview.testFiles.join("\n")}\n`);
  process.exit(0);
}

const asJson = args.includes("--json");
const dryRun = args.includes("--dry-run");
if (dryRun || asJson) {
  if (asJson) {
    process.stdout.write(`${JSON.stringify(preview, null, 2)}\n`);
  } else {
    process.stdout.write(renderPreview(preview));
  }
  process.exit(0);
}

const timeoutMs = parseOptionalInteger(readFlagValue(args, "--timeout-ms"), "--timeout-ms");
const result = spawnSync(preview.invocation.command, preview.invocation.args, {
  cwd: preview.cwd,
  stdio: "inherit",
  timeout: timeoutMs ?? undefined,
});

if (result.error) {
  process.stderr.write(`${result.error.stack ?? result.error.message}\n`);
  process.exit(result.status ?? 1);
}

process.exit(result.status ?? 1);

function readFlagValue(argv, flagName) {
  const index = argv.indexOf(flagName);
  if (index === -1 || index === argv.length - 1) {
    return null;
  }

  return argv[index + 1];
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

function renderPreview(preview) {
  const lines = [];
  lines.push(`Suite: ${preview.suiteName}`);
  lines.push(`Cwd: ${preview.cwd}`);
  lines.push(`Tests: ${preview.testCount}`);
  lines.push(`Command: ${preview.invocation.displayCommand}`);
  lines.push("Files:");
  for (const testFile of preview.testFiles) {
    lines.push(`- ${testFile}`);
  }

  return `${lines.join("\n")}\n`;
}

function printUsageAndExit(exitCode, message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }

  process.stderr.write(
    "Usage: node scripts/runtime/run-runtime-host-reliability-suite.mjs [--list] [--dry-run] [--json] [--timeout-ms <n>] [-- <node --test args...>]\n",
  );
  process.exit(exitCode);
}
