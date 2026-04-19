import process from "node:process";
import { writeFileSync } from "node:fs";
import { resolveRepoPath } from "./orchestration-lib.mjs";
import {
  buildRuntimeAttemptScorecard,
  loadRuntimeAttemptLedger,
  renderRuntimeAttemptScorecardText,
} from "./runtime-attempt-ledger-lib.mjs";

const args = process.argv.slice(2);
const inputPath = readFlagValue(args, "--input");
const outputPath = readFlagValue(args, "--output");
const format = normalizeFormat(args);

if (!inputPath) {
  printUsageAndExit("Missing --input.");
}

const resolvedInputPath = resolveRepoPath(inputPath);
const entries = loadRuntimeAttemptLedger(resolvedInputPath);
const scorecard = buildRuntimeAttemptScorecard(entries, {
  inputFile: resolvedInputPath,
});

const serialized =
  format === "text"
    ? renderRuntimeAttemptScorecardText(scorecard)
    : `${JSON.stringify(scorecard, null, 2)}\n`;

if (outputPath) {
  writeFileSync(resolveRepoPath(outputPath), serialized, "utf8");
} else {
  process.stdout.write(serialized);
}

process.exit(0);

function normalizeFormat(argv) {
  if (argv.includes("--json")) {
    return "json";
  }

  return readFlagValue(argv, "--format") ?? "text";
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
    "Usage: node scripts/runtime/summarize-runtime-attempt-ledger.mjs --input <file> [--output <file>] [--format text|json]\n",
  );
  process.exit(1);
}
