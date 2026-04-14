import { pathToFileURL } from "node:url";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { buildCodexThreadAuditDoctorReport } from "../src/codex-thread-audit-doctor.mjs";

export function parseCodexThreadAuditDoctorArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const days = Number.parseInt(getArg(list, "stale-synthetic-days") || "", 10);
  return {
    json: hasFlag(list, "json"),
    staleSyntheticDays: Number.isFinite(days) && days >= 0 ? days : 7
  };
}

export async function runCodexThreadAuditDoctor(args = process.argv.slice(2), runtime = {}) {
  const command = parseCodexThreadAuditDoctorArgs(args);
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const report = buildCodexThreadAuditDoctorReport(config, {
    now: runtime.now || new Date(),
    staleSyntheticDays: command.staleSyntheticDays
  });

  if (command.json) {
    writer.log(JSON.stringify(report, null, 2));
    return report;
  }

  writer.log("Codex Thread Audit Doctor");
  writer.log("");
  writer.log(
    `Summary: status=${report.status}, fail=${report.fail_count}, warn=${report.warn_count}, staleSyntheticDays=${report.stale_synthetic_days}`
  );
  for (const check of report.checks) {
    writer.log(`[${check.status.toUpperCase()}] ${check.id}: ${check.summary}`);
  }

  return report;
}

function getArg(args, name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }
  return args[index + 1];
}

function hasFlag(args, name) {
  return args.includes(`--${name}`);
}

function printUsage(writer = console.error) {
  writer("Usage: node scripts/codex-thread-audit-doctor.mjs [--json] [--stale-synthetic-days <N>]");
}

async function main(args = process.argv.slice(2)) {
  if (args.includes("--help") || args.includes("-h")) {
    printUsage(console.error);
    process.exit(0);
  }

  try {
    const report = await runCodexThreadAuditDoctor(args);
    process.exit(report.status === "fail" ? 1 : 0);
  } catch (error) {
    printUsage(console.error);
    console.error("");
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

function isDirectExecution() {
  if (!process.argv[1]) {
    return false;
  }
  try {
    return pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
  } catch {
    return false;
  }
}

if (isDirectExecution()) {
  await main();
}
