import { readFileSync } from "node:fs";
import process from "node:process";
import {
  validateStructuredVerifierReport,
  validateCompactionSummary,
  validateWorkerOutput,
} from "./orchestration-lib.mjs";

const args = process.argv.slice(2);
const inputPath = readFlagValue(args, "--input");
const mode = readFlagValue(args, "--mode") ?? "worker";
const format = normalizeFormat(args);

if (!inputPath) {
  printUsageAndExit();
}

if (!["worker", "compaction", "structured-verifier"].includes(mode)) {
  printUsageAndExit(`Unsupported mode "${mode}".`);
}

const input = readFileSync(inputPath, "utf8");
const report =
  mode === "compaction"
    ? validateCompactionSummary(input)
    : mode === "structured-verifier"
      ? validateStructuredVerifierReport(input)
      : validateWorkerOutput(input);

if (format === "json") {
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} else {
  process.stdout.write(renderTextReport(mode, report));
}

process.exit(report.ok ? 0 : 1);

function normalizeFormat(argv) {
  if (argv.includes("--json")) {
    return "json";
  }

  return readFlagValue(argv, "--format") ?? "text";
}

function renderTextReport(mode, report) {
  const lines = [];
  lines.push(`Verification mode: ${mode}`);
  for (const item of report.checklist) {
    lines.push(`- ${item.name}: ${item.ok ? "PASS" : "FAIL"} - ${item.detail}`);
  }
  if (report.invalidFields?.length > 0) {
    lines.push(`- invalid_fields: ${report.invalidFields.join(", ")}`);
  }
  lines.push(`VERDICT: ${report.verdict}`);
  return `${lines.join("\n")}\n`;
}

function readFlagValue(argv, flagName) {
  const index = argv.indexOf(flagName);
  if (index === -1 || index === argv.length - 1) {
    return null;
  }

  return argv[index + 1];
}

function printUsageAndExit(message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }
  process.stderr.write(
    "Usage: node scripts/runtime/run-verification-pass.mjs --input <file> [--mode worker|compaction|structured-verifier] [--format text|json]\n",
  );
  process.exit(1);
}
