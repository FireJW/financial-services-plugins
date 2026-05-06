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
    continueOnError: true
  };
  let sawContinue = false;
  let sawFailFast = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--queries-file") {
      parsed.queriesFile = String(args[++index] || "");
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
