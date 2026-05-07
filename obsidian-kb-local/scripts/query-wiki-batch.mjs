import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { isCliEntrypoint } from "../src/cli-entrypoint.mjs";
import { rebuildAutomaticLinks } from "../src/link-graph.mjs";
import { refreshWikiViews } from "../src/wiki-views.mjs";
import { executeQueryWikiCommand } from "./query-wiki.mjs";

export function parseQueriesFromText(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
}

export function parseQueryWikiBatchCliArgs(args = []) {
  const parsed = {
    queriesFile: "",
    continueOnError: true,
    topic: "",
    dryRun: true,
    execute: false,
    skipLinks: true,
    skipViews: true
  };
  let sawContinue = false;
  let sawFailFast = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--queries-file") {
      parsed.queriesFile = String(args[++index] || "");
    } else if (arg === "--topic") {
      parsed.topic = String(args[++index] || "");
    } else if (arg === "--execute") {
      parsed.execute = true;
      parsed.dryRun = false;
      parsed.skipLinks = false;
      parsed.skipViews = false;
    } else if (arg === "--dry-run") {
      parsed.execute = false;
      parsed.dryRun = true;
      parsed.skipLinks = true;
      parsed.skipViews = true;
    } else if (arg === "--skip-links") {
      parsed.skipLinks = true;
    } else if (arg === "--skip-views") {
      parsed.skipViews = true;
    } else if (arg === "--continue-on-error") {
      sawContinue = true;
      parsed.continueOnError = true;
    } else if (arg === "--fail-fast") {
      sawFailFast = true;
      parsed.continueOnError = false;
    }
  }

  if (sawContinue && sawFailFast) {
    throw new Error("Choose either --continue-on-error or --fail-fast, not both.");
  }

  return parsed;
}

export async function runQueryWikiBatchCli(args = process.argv.slice(2), runtime = {}) {
  const writer = runtime.writer || console;
  if (args.includes("--help") || args.includes("-h")) {
    printUsage(writer);
    return 0;
  }

  try {
    const command = parseQueryWikiBatchCliArgs(args);
    if (!command.queriesFile) {
      const error = new Error("Missing required --queries-file argument.");
      error.code = "USAGE";
      throw error;
    }

    const queriesPath = path.resolve(command.queriesFile);
    const queries = parseQueriesFromText(fs.readFileSync(queriesPath, "utf8"));
    if (queries.length === 0) {
      const error = new Error(`No queries found in ${queriesPath}.`);
      error.code = "USAGE";
      throw error;
    }

    const config = runtime.config || loadConfig();
    const summary = await runQueryWikiBatch(
      {
        ...command,
        queries
      },
      {
        ...runtime,
        config,
        writer
      }
    );
    writer.log(
      `Batch summary: total=${summary.total}, completed=${summary.completed}, failed=${summary.failed}`
    );
    return summary.failed > 0 ? 1 : 0;
  } catch (error) {
    if (error?.code === "USAGE") {
      printUsage(writer);
      writer.error?.("");
    }
    writer.error?.(error instanceof Error ? error.message : String(error));
    return 1;
  }
}

export async function runQueryWikiBatch(command, runtime = {}) {
  const runSingleQuery = runtime.runSingleQuery || ((single) => executeQueryWikiCommand(single, runtime));
  const writer = runtime.writer || console;
  const successes = [];
  const failures = [];

  for (const query of command.queries || []) {
    const singleCommand = {
      ...command,
      query,
      skipLinks: true,
      skipViews: true
    };
    try {
      const result = await runSingleQuery(singleCommand);
      successes.push(result);
    } catch (error) {
      failures.push({ query, error: error.message || String(error) });
      writer.error?.(error.message || String(error));
      if (!command.continueOnError) {
        break;
      }
    }
  }

  let linkResult = null;
  let viewResults = [];
  if (successes.length > 0 && !command.skipLinks) {
    const rebuildLinksFn = runtime.rebuildLinksFn || rebuildAutomaticLinks;
    linkResult = rebuildLinksFn(runtime.config, {
      allowFilesystemFallback: true,
      preferCli: true
    });
  }
  if (successes.length > 0 && !command.skipViews) {
    const refreshViewsFn = runtime.refreshViewsFn || refreshWikiViews;
    viewResults = refreshViewsFn(runtime.config, {
      allowFilesystemFallback: true,
      preferCli: true
    });
  }

  return {
    total: (command.queries || []).length,
    completed: successes.length,
    failed: failures.length,
    failures,
    linkResult,
    viewResults
  };
}

function printUsage(writer = console.error) {
  const write =
    typeof writer === "function"
      ? writer
      : writer?.error?.bind(writer) || writer?.log?.bind(writer) || console.error;
  write(
    "Usage: node scripts/query-wiki-batch.mjs --queries-file <path> [--topic <topic>] [--dry-run|--execute] [--continue-on-error|--fail-fast]"
  );
}

if (isCliEntrypoint(import.meta.url)) {
  const exitCode = await runQueryWikiBatchCli();
  process.exit(exitCode);
}
