import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadConfig } from "../src/config.mjs";
import {
  CODEX_THREAD_AUDIT_LOG_PATTERNS,
  isArchivableAuditEntry
} from "../src/codex-thread-audit-utils.mjs";

const DEFAULT_DAYS = 7;

export function parsePruneCodexThreadAuditLogsArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const days = normalizeDays(getArg(list, "days"), DEFAULT_DAYS);
  return {
    apply: hasFlag(list, "apply"),
    days,
    json: hasFlag(list, "json")
  };
}

export function buildPruneCodexThreadAuditLogsPlan(config, command, now = new Date()) {
  const logDirectory = path.join(config.projectRoot, "logs");
  const archiveDirectory = path.join(logDirectory, "archive");
  const cutoff = new Date(now.getTime() - command.days * 24 * 60 * 60 * 1000);
  const files = fs.existsSync(logDirectory)
    ? fs.readdirSync(logDirectory).filter((fileName) =>
        Object.values(CODEX_THREAD_AUDIT_LOG_PATTERNS).some((pattern) => pattern.test(fileName))
      )
    : [];

  const filePlans = [];
  for (const fileName of files) {
    const fullPath = path.join(logDirectory, fileName);
    const lines = fs.readFileSync(fullPath, "utf8").split(/\r?\n/).filter(Boolean);
    const kept = [];
    const archived = [];

    for (const line of lines) {
      let entry;
      try {
        entry = JSON.parse(line);
      } catch {
        kept.push(line);
        continue;
      }

      if (isArchivableAuditEntry(entry, cutoff)) {
        archived.push(JSON.stringify(entry));
      } else {
        kept.push(line);
      }
    }

    if (archived.length === 0) {
      continue;
    }

    filePlans.push({
      fileName,
      sourcePath: fullPath,
      archivePath: path.join(archiveDirectory, fileName),
      archivedCount: archived.length,
      keptCount: kept.length,
      archivedLines: archived,
      keptLines: kept
    });
  }

  return {
    apply: command.apply,
    days: command.days,
    cutoff: cutoff.toISOString(),
    archiveDirectory,
    filePlans,
    archivedEntries: filePlans.reduce((sum, plan) => sum + plan.archivedCount, 0)
  };
}

export function executePruneCodexThreadAuditLogsPlan(plan) {
  if (!plan.apply || plan.filePlans.length === 0) {
    return plan;
  }

  fs.mkdirSync(plan.archiveDirectory, { recursive: true });
  for (const filePlan of plan.filePlans) {
    fs.appendFileSync(filePlan.archivePath, `${filePlan.archivedLines.join("\n")}\n`, "utf8");
    const nextContent = filePlan.keptLines.length > 0 ? `${filePlan.keptLines.join("\n")}\n` : "";
    fs.writeFileSync(filePlan.sourcePath, nextContent, "utf8");
  }

  return plan;
}

export async function runPruneCodexThreadAuditLogs(args = process.argv.slice(2), runtime = {}) {
  const command = parsePruneCodexThreadAuditLogsArgs(args);
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const plan = buildPruneCodexThreadAuditLogsPlan(config, command, runtime.now || new Date());
  executePruneCodexThreadAuditLogsPlan(plan);

  if (command.json) {
    writer.log(
      JSON.stringify(
        {
          apply: plan.apply,
          days: plan.days,
          cutoff: plan.cutoff,
          archivedEntries: plan.archivedEntries,
          files: plan.filePlans.map((entry) => ({
            fileName: entry.fileName,
            archivedCount: entry.archivedCount,
            keptCount: entry.keptCount,
            archivePath: entry.archivePath
          }))
        },
        null,
        2
      )
    );
    return plan;
  }

  writer.log(
    `Prune summary: apply=${plan.apply}, days=${plan.days}, archivedEntries=${plan.archivedEntries}, files=${plan.filePlans.length}`
  );
  for (const filePlan of plan.filePlans) {
    writer.log(
      `- ${filePlan.fileName}: archived=${filePlan.archivedCount}, kept=${filePlan.keptCount}, archive=${filePlan.archivePath}`
    );
  }

  return plan;
}
function normalizeDays(rawValue, fallbackValue) {
  const parsed = Number.parseInt(String(rawValue ?? ""), 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallbackValue;
  }
  return parsed;
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
  writer("Usage: node scripts/prune-codex-thread-audit-logs.mjs [--days <N>] [--apply] [--json]");
}

async function main(args = process.argv.slice(2)) {
  if (args.includes("--help") || args.includes("-h")) {
    printUsage(console.error);
    process.exit(0);
  }

  try {
    await runPruneCodexThreadAuditLogs(args);
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
