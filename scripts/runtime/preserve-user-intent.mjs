import { readFileSync, writeFileSync } from "node:fs";
import process from "node:process";
import { buildIntentPayload } from "./orchestration-lib.mjs";

const args = process.argv.slice(2);
const inputPath =
  readFlagValue(args, "--input") ?? readFlagValue(args, "--intent-file");
const currentState = readFlagValue(args, "--current-state");
const nextStep = readFlagValue(args, "--next-step");
const outputPath = readFlagValue(args, "--output");
const format = normalizeFormat(args);
const outputKind = readFlagValue(args, "--output-kind") ?? "compaction";

if (!inputPath) {
  console.error(
    "Usage: node scripts/runtime/preserve-user-intent.mjs --input <file> [--current-state <text>] [--next-step <text>] [--output-kind intent|compaction] [--format text|json] [--output <file>]",
  );
  process.exit(1);
}

if (!["intent", "compaction"].includes(outputKind)) {
  console.error(`Unsupported --output-kind value "${outputKind}". Use intent or compaction.`);
  process.exit(1);
}

const rawInput = readFileSync(inputPath, "utf8");
const payload = buildIntentPayload(rawInput, {
  currentState,
  nextStep,
});

const serialized =
  format === "json"
    ? `${JSON.stringify(payload, null, 2)}\n`
    : outputKind === "intent"
      ? payload.intentMarkdown
      : payload.compactSummary;

if (outputPath) {
  writeFileSync(outputPath, serialized, "utf8");
} else {
  process.stdout.write(serialized);
}

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
