import process from "node:process";
import {
  RUNTIME_COMPATIBILITY_PROBES,
  buildRuntimeCompatibilitySuitePreview,
  runRuntimeCompatibilitySuite,
} from "./runtime-compatibility-suite-lib.mjs";

const rawArgs = process.argv.slice(2);
const args = [...rawArgs];

if (args.includes("--help")) {
  printUsageAndExit(0);
}

const requestedPluginDirs = readFlagValues(args, "--plugin-dir");
const timeoutMs = parseOptionalInteger(readFlagValue(args, "--timeout-ms"), "--timeout-ms");
const requireBuiltRuntime = args.includes("--require-built-runtime");
const asJson = args.includes("--json");
const dryRun = args.includes("--dry-run");
const listOnly = args.includes("--list");
const checkMode = args.includes("--check");

const preview = buildRuntimeCompatibilitySuitePreview({
  requestedPluginDirs,
  timeoutMs,
  requireBuiltRuntime,
});

if (listOnly) {
  process.stdout.write(
    `${RUNTIME_COMPATIBILITY_PROBES.map((probe) => probe.scriptPath).join("\n")}\n`,
  );
  process.exit(0);
}

if (dryRun) {
  if (asJson) {
    process.stdout.write(`${JSON.stringify(preview, null, 2)}\n`);
  } else {
    process.stdout.write(renderPreview(preview));
  }
  process.exit(0);
}

const report = runRuntimeCompatibilitySuite({
  requestedPluginDirs,
  timeoutMs,
  requireBuiltRuntime,
});

if (asJson) {
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} else {
  process.stdout.write(renderReport(report));
}

if (checkMode || !report.summary.checkPassed) {
  process.exit(report.summary.checkPassed ? 0 : 1);
}

process.exit(0);

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
  lines.push(`Runtime built: ${preview.vendorRuntimeBuilt}`);
  lines.push(`Probes: ${preview.probeCount}`);
  lines.push(`Command: ${preview.invocation.displayCommand}`);
  lines.push("Probe scripts:");
  for (const probe of preview.probes) {
    lines.push(`- ${probe.scriptPath}`);
  }

  return `${lines.join("\n")}\n`;
}

function renderReport(report) {
  const lines = [];
  lines.push(`Suite: ${report.suiteName}`);
  lines.push(`Runtime built: ${report.vendorRuntimeBuilt}`);
  lines.push(`Status: ${report.summary.status}`);
  lines.push(`Check passed: ${report.summary.checkPassed}`);
  lines.push(`Successful probes: ${report.summary.successfulProbeCount}/${report.summary.probeCount}`);

  if (report.skippedVendorUnbuilt) {
    lines.push(`Skip reason: Recovered runtime is not built. Expected ${report.cliPath}`);
  }

  lines.push("Probes:");
  for (const probe of report.probes) {
    const state = probe.skipped ? "SKIPPED" : probe.ok ? "OK" : "FAIL";
    lines.push(`- ${probe.label}: ${state}`);
    if (probe.error) {
      lines.push(`  ${probe.error.split(/\r?\n/)[0]}`);
    }
  }

  return `${lines.join("\n")}\n`;
}

function printUsageAndExit(exitCode, message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }

  process.stderr.write(
    "Usage: node scripts/runtime/run-runtime-compatibility-suite.mjs [--list] [--dry-run] [--json] [--check] [--require-built-runtime] [--plugin-dir <path>] [--timeout-ms <n>]\n",
  );
  process.exit(exitCode);
}
