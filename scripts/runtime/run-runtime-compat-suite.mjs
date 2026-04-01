import process from "node:process";
import {
  RUNTIME_COMPAT_PROBES,
  buildRuntimeCompatSuitePreview,
  getRuntimeCompatSuiteExitCode,
  renderRuntimeCompatSuitePreview,
  renderRuntimeCompatSuiteReport,
  runRuntimeCompatSuite,
} from "./runtime-compat-suite-lib.mjs";

const args = process.argv.slice(2);

if (args.includes("--help")) {
  printUsageAndExit(0);
}

const pluginDirs = readFlagValues(args, "--plugin-dir");
const timeoutMs = parseOptionalInteger(readFlagValue(args, "--timeout-ms"), "--timeout-ms");
const requireBuiltRuntime = args.includes("--require-built-runtime");
const dryRun = args.includes("--dry-run");
const asJson = args.includes("--json");

if (args.includes("--list")) {
  process.stdout.write(`${RUNTIME_COMPAT_PROBES.map((probe) => probe.scriptPath).join("\n")}\n`);
  process.exit(0);
}

if (dryRun) {
  const preview = buildRuntimeCompatSuitePreview({
    pluginDirs,
    timeoutMs: timeoutMs ?? undefined,
    requireBuiltRuntime,
  });
  process.stdout.write(
    asJson ? `${JSON.stringify(preview, null, 2)}\n` : renderRuntimeCompatSuitePreview(preview),
  );
  process.exit(0);
}

const report = runRuntimeCompatSuite({
  pluginDirs,
  timeoutMs: timeoutMs ?? undefined,
  requireBuiltRuntime,
});

process.stdout.write(
  asJson ? `${JSON.stringify(report, null, 2)}\n` : renderRuntimeCompatSuiteReport(report),
);
process.exit(getRuntimeCompatSuiteExitCode(report));

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

function printUsageAndExit(exitCode, message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }

  process.stderr.write(
    "Usage: node scripts/runtime/run-runtime-compat-suite.mjs [--plugin-dir <path>]... [--list] [--dry-run] [--json] [--require-built-runtime] [--timeout-ms <n>]\n",
  );
  process.exit(exitCode);
}
