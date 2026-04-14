import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { captureCodexThreadToVault } from "../src/codex-thread-capture.mjs";
import { loadConfig } from "../src/config.mjs";
import { readTextFromStdin } from "../src/stdin-text.mjs";

const DEFAULT_TIMEOUT_MS = 180000;

export function parseCaptureCodexThreadArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const threadUri = getArg(list, "thread-uri");
  const threadId = getArg(list, "thread-id");
  const topic = getArg(list, "topic");
  const title = getArg(list, "title");
  const filenameBase = getArg(list, "filename-base");
  const bodyFile = getArg(list, "body-file");
  const sourceLabel = getArg(list, "source-label");
  const capturedAt = getArg(list, "captured-at");
  const runId = getArg(list, "run-id");
  const status = getArg(list, "status") || "queued";
  const compile = hasFlag(list, "compile");
  const timeoutMs = normalizeTimeoutMs(getArg(list, "timeout-ms"), DEFAULT_TIMEOUT_MS);

  return {
    threadUri,
    threadId,
    topic,
    title,
    filenameBase,
    bodyFile,
    sourceLabel,
    capturedAt,
    runId,
    status,
    compile,
    timeoutMs
  };
}

export async function runCaptureCodexThread(args = process.argv.slice(2), runtime = {}) {
  const command = parseCaptureCodexThreadArgs(args);
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const body = command.bodyFile
    ? fs.readFileSync(path.resolve(command.bodyFile), "utf8")
    : await (runtime.readTextFromStdin || readTextFromStdin)();

  const result = await captureCodexThreadToVault(
    config,
    {
      threadUri: command.threadUri,
      threadId: command.threadId,
      topic: command.topic,
      title: command.title,
      filenameBase: command.filenameBase,
      body,
      sourceLabel: command.sourceLabel,
      capturedAt: command.capturedAt,
      status: command.status
    },
    {
      runId: command.runId,
      compile: command.compile,
      timeoutMs: command.timeoutMs,
      allowFilesystemFallback: true,
      preferCli: true
    }
  );

  writer.log(`Captured raw note: ${result.ingestResult.path} (${result.ingestResult.mode})`);
  if (result.compileResult) {
    if (!result.compileResult.ok) {
      writer.log(`Compile failed: ${result.compileResult.error.message}`);
      writer.log(`Compile log: ${result.compileResult.logFile}`);
    } else {
      writer.log(`Compile endpoint: ${result.compileResult.response.endpoint}`);
      writer.log(`Compile log: ${result.compileResult.applyResult.logFile}`);
      for (const entry of result.compileResult.applyResult.results) {
        if (entry.path) {
          writer.log(`- ${entry.action}: ${entry.path} (${entry.mode})`);
        }
      }
    }
  }

  if (result.linkResult) {
    writer.log(
      `Links rebuilt: ${result.linkResult.updated}/${result.linkResult.scanned}`
    );
  }
  if (result.viewResults) {
    writer.log(
      `Views refreshed: ${result.viewResults.map((entry) => entry.path).join(", ")}`
    );
  }

  return result;
}

function printUsage() {
  console.error(
    "Usage: node scripts/capture-codex-thread.mjs [--thread-uri <codex://threads/...>|--thread-id <id>] --topic <topic> --title <title> [--body-file <path>] [--compile] [--timeout-ms N]"
  );
  console.error("  Body content is read from stdin unless --body-file is provided.");
  console.error("  If no thread URI is provided, the command falls back to codex://threads/current-thread.");
}

async function main(args = process.argv.slice(2)) {
  if (hasFlag(args, "help") || hasFlag(args, "h")) {
    printUsage();
    process.exit(0);
  }

  try {
    await runCaptureCodexThread(args);
  } catch (error) {
    printUsage();
    console.error("");
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
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

function normalizeTimeoutMs(rawValue, fallbackMs) {
  const parsed = Number.parseInt(String(rawValue ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return fallbackMs;
  }

  if (parsed <= 0) {
    return 0;
  }

  return parsed;
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
