import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadConfig } from "../src/config.mjs";
import { buildBackfilledAuditRunId } from "../src/codex-thread-capture-log.mjs";
import { CODEX_THREAD_AUDIT_LOG_PATTERNS } from "../src/codex-thread-audit-utils.mjs";

export function parseBackfillCodexThreadAuditRunIdsArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  return {
    apply: hasFlag(list, "apply"),
    json: hasFlag(list, "json")
  };
}

export function buildBackfillCodexThreadAuditRunIdsPlan(config) {
  const logDirectory = path.join(config.projectRoot, "logs");
  const filePlans = [];

  if (!fs.existsSync(logDirectory)) {
    return {
      logDirectory,
      filePlans,
      updatedEntries: 0
    };
  }

  for (const [logType, pattern] of Object.entries(CODEX_THREAD_AUDIT_LOG_PATTERNS)) {
    const fileNames = fs.readdirSync(logDirectory).filter((fileName) => pattern.test(fileName));
    for (const fileName of fileNames) {
      const fullPath = path.join(logDirectory, fileName);
      const lines = fs.readFileSync(fullPath, "utf8").split(/\r?\n/).filter(Boolean);
      const nextLines = [];
      let updatedCount = 0;

      for (const [index, line] of lines.entries()) {
        let entry;
        try {
          entry = JSON.parse(line);
        } catch {
          nextLines.push(line);
          continue;
        }

        if (!String(entry.run_id || "").trim()) {
          entry.run_id = buildBackfilledAuditRunId(entry, { logType, index });
          entry.run_id_source = "backfill";
          updatedCount += 1;
        }

        nextLines.push(JSON.stringify(entry));
      }

      if (updatedCount > 0) {
        filePlans.push({
          logType,
          fileName,
          path: fullPath,
          updatedCount,
          nextLines
        });
      }
    }
  }

  return {
    logDirectory,
    filePlans,
    updatedEntries: filePlans.reduce((sum, plan) => sum + plan.updatedCount, 0)
  };
}

export function executeBackfillCodexThreadAuditRunIdsPlan(plan, apply = false) {
  if (!apply) {
    return plan;
  }

  for (const filePlan of plan.filePlans) {
    fs.writeFileSync(filePlan.path, `${filePlan.nextLines.join("\n")}\n`, "utf8");
  }

  return plan;
}

export async function runBackfillCodexThreadAuditRunIds(args = process.argv.slice(2), runtime = {}) {
  const command = parseBackfillCodexThreadAuditRunIdsArgs(args);
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const plan = buildBackfillCodexThreadAuditRunIdsPlan(config);
  executeBackfillCodexThreadAuditRunIdsPlan(plan, command.apply);

  if (command.json) {
    writer.log(
      JSON.stringify(
        {
          apply: command.apply,
          updatedEntries: plan.updatedEntries,
          files: plan.filePlans.map((entry) => ({
            fileName: entry.fileName,
            logType: entry.logType,
            updatedCount: entry.updatedCount
          }))
        },
        null,
        2
      )
    );
    return plan;
  }

  writer.log(`Backfill summary: apply=${command.apply}, updatedEntries=${plan.updatedEntries}, files=${plan.filePlans.length}`);
  for (const filePlan of plan.filePlans) {
    writer.log(`- ${filePlan.fileName}: updated=${filePlan.updatedCount}`);
  }

  return plan;
}

function hasFlag(args, name) {
  return args.includes(`--${name}`);
}

function printUsage(writer = console.error) {
  writer("Usage: node scripts/backfill-codex-thread-audit-run-ids.mjs [--apply] [--json]");
}

async function main(args = process.argv.slice(2)) {
  if (args.includes("--help") || args.includes("-h")) {
    printUsage(console.error);
    process.exit(0);
  }

  try {
    await runBackfillCodexThreadAuditRunIds(args);
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
