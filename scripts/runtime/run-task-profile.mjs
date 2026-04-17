import process from "node:process";
import { buildTaskProfilePreview, loadTaskProfiles } from "./orchestration-lib.mjs";
import { runRuntimeCli } from "./runtime-report-lib.mjs";

const rawArgs = process.argv.slice(2);
const separatorIndex = rawArgs.indexOf("--");
const args = separatorIndex === -1 ? rawArgs : rawArgs.slice(0, separatorIndex);
const forwardedArgs = separatorIndex === -1 ? [] : rawArgs.slice(separatorIndex + 1);

if (args.includes("--list")) {
  const config = loadTaskProfiles();
  const profiles = Object.keys(config.profiles).sort();
  process.stdout.write(`${profiles.join("\n")}\n`);
  process.exit(0);
}

const profileName = readFlagValue(args, "--profile");
if (!profileName) {
  printUsageAndExit();
}

const timeoutMs = Number.parseInt(readFlagValue(args, "--timeout-ms") ?? "", 10);
const options = {
  pluginDirs: readFlagValues(args, "--plugin-dir"),
  allPlugins: args.includes("--all-plugins"),
  includePartnerBuilt: args.includes("--include-partner-built"),
  forwardedArgs,
};

const preview = buildTaskProfilePreview(profileName, options);
const asJson = args.includes("--json");
const dryRun = args.includes("--dry-run");

if (dryRun || asJson) {
  if (asJson) {
    process.stdout.write(
      `${JSON.stringify(dryRun ? preview : preview.profile, null, 2)}\n`,
    );
  } else {
    process.stdout.write(renderPreview(preview));
  }
  process.exit(0);
}

const result = runRuntimeCli(preview.invocation.cliArgs, {
  timeout: Number.isFinite(timeoutMs) ? timeoutMs : undefined,
});

if (result.stdout) {
  process.stdout.write(result.stdout);
}

if (result.stderr) {
  process.stderr.write(result.stderr);
}

process.exit(result.status ?? 1);

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
      printUsageAndExit(`Missing value for ${flagName}.`);
    }

    values.push(argv[index + 1]);
    index += 1;
  }

  return values;
}

function renderPreview(preview) {
  const lines = [];
  lines.push(`Profile: ${preview.profile.name}`);
  lines.push(`Purpose: ${preview.profile.purpose}`);
  lines.push(`Model tier: ${preview.profile.modelTier}`);
  lines.push(`Thinking budget: ${preview.profile.thinkingBudget}`);
  lines.push(`Max turns: ${preview.profile.maxTurns}`);
  lines.push(`Requires contract: ${preview.profile.requiresContract}`);
  lines.push(`Verification only: ${preview.profile.verificationOnly}`);
  lines.push("Plugin dirs:");
  for (const pluginDir of preview.invocation.pluginDirs) {
    lines.push(`- ${pluginDir}`);
  }
  lines.push("CLI args:");
  for (const cliArg of preview.invocation.cliArgs) {
    lines.push(`- ${cliArg}`);
  }

  return `${lines.join("\n")}\n`;
}

function printUsageAndExit(message) {
  if (message) {
    process.stderr.write(`${message}\n`);
  }
  process.stderr.write(
    "Usage: node scripts/runtime/run-task-profile.mjs --list | --profile <name> [--dry-run] [--json] [--plugin-dir <path>] [--all-plugins] [--include-partner-built] [--timeout-ms <n>] [-- <runtime args...>]\n",
  );
  process.exit(1);
}
