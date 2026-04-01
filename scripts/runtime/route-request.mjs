import process from "node:process";
import { readFileSync } from "node:fs";
import { renderRoutePlan, routeRequest } from "./request-router-lib.mjs";

const args = process.argv.slice(2);

if (args.includes("--help")) {
  printUsageAndExit(0);
}

const inputFile = readFlagValue(args, "--input-file");
const requestFromFlag = readFlagValue(args, "--request");
const requestFromArgs = readRemainingText(args);
const requestText = requestFromFlag ?? requestFromArgs ?? readInputFile(inputFile);

if (!requestText?.trim()) {
  printUsageAndExit(1, "Provide request text via --request, --input-file, or trailing arguments.");
}

const plan = routeRequest(requestText, {
  routeId: readFlagValue(args, "--route"),
  classicCaseId: readFlagValue(args, "--classic-case"),
  profile: readFlagValue(args, "--profile"),
  pluginDirs: readFlagValues(args, "--plugin-dir"),
  noAutoRoute: args.includes("--no-auto-route"),
});

if (args.includes("--json")) {
  process.stdout.write(`${JSON.stringify(plan, null, 2)}\n`);
  process.exit(0);
}

process.stdout.write(renderRoutePlan(plan, { trace: args.includes("--trace") }));
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

function readRemainingText(argv) {
  const consumedFlags = new Set([
    "--input-file",
    "--request",
    "--route",
    "--classic-case",
    "--profile",
    "--plugin-dir",
  ]);
  const freeArgs = [];

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (
      consumedFlags.has(value) &&
      index < argv.length - 1
    ) {
      index += 1;
      continue;
    }

    if (value.startsWith("--")) {
      continue;
    }

    freeArgs.push(value);
  }

  return freeArgs.length > 0 ? freeArgs.join(" ") : null;
}

function readInputFile(inputFile) {
  if (!inputFile) {
    return null;
  }

  return readFileSync(inputFile, "utf8");
}

function printUsageAndExit(exitCode, message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }

  process.stderr.write(
    "Usage: node scripts/runtime/route-request.mjs [--request <text> | --input-file <path> | trailing text] [--route <id>] [--classic-case <id>] [--profile <profile>] [--plugin-dir <path>] [--no-auto-route] [--trace] [--json]\n",
  );
  process.exit(exitCode);
}
