import { readFileSync, writeFileSync } from "node:fs";
import process from "node:process";
import { buildSessionStatePayload } from "./orchestration-lib.mjs";

const args = process.argv.slice(2);
const inputPath = readFlagValue(args, "--input");
const outputPath = readFlagValue(args, "--output");
const format = normalizeFormat(args);

const input = inputPath ? JSON.parse(readFileSync(inputPath, "utf8")) : {};
const payload = buildSessionStatePayload(input);
const serialized =
  format === "json"
    ? `${JSON.stringify(payload, null, 2)}\n`
    : payload.markdown;

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
