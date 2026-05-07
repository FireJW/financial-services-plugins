import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  appendCodexThreadCaptureAuditLog,
  normalizeAuditRunId
} from "../src/codex-thread-capture-log.mjs";
import { loadConfig } from "../src/config.mjs";
import { loadCodexLlmProvider, summarizeLlmProvider } from "../src/codex-config.mjs";
import { captureCodexThreadToVault } from "../src/codex-thread-capture.mjs";
import { rebuildAutomaticLinks } from "../src/link-graph.mjs";
import { refreshWikiViews } from "../src/wiki-views.mjs";

const DEFAULT_TIMEOUT_MS = 180000;

export function parseCaptureCodexThreadBatchArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const manifestPath = String(getArg(list, "manifest") || "").trim();
  const compile = hasFlag(list, "compile");
  const dryRun = hasFlag(list, "dry-run");
  const runId = String(getArg(list, "run-id") || "").trim();
  const skipLinks = hasFlag(list, "skip-links");
  const skipViews = hasFlag(list, "skip-views");
  const explicitContinueOnError = hasFlag(list, "continue-on-error");
  const explicitFailFast = hasFlag(list, "fail-fast");
  const continueOnError = explicitContinueOnError ? true : !explicitFailFast;
  const timeoutMs = normalizeTimeoutMs(getArg(list, "timeout-ms"), DEFAULT_TIMEOUT_MS);

  if (!manifestPath) {
    throw new Error("Missing required --manifest argument.");
  }
  if (explicitContinueOnError && explicitFailFast) {
    throw new Error("Choose either --continue-on-error or --fail-fast, not both.");
  }

  return {
    manifestPath: path.resolve(manifestPath),
    compile,
    dryRun,
    runId,
    skipLinks,
    skipViews,
    continueOnError,
    timeoutMs
  };
}

export function loadCodexThreadBatchManifest(manifestPath) {
  const resolvedPath = path.resolve(String(manifestPath || ""));
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Manifest file does not exist: ${resolvedPath}`);
  }

  let parsed;
  try {
    parsed = JSON.parse(stripUtf8Bom(fs.readFileSync(resolvedPath, "utf8")));
  } catch (error) {
    throw new Error(`Failed to parse codex thread batch manifest JSON: ${error.message}`);
  }

  const defaults = normalizeBatchDefaults(parsed?.defaults);
  const rawEntries = Array.isArray(parsed) ? parsed : parsed?.entries;
  if (!Array.isArray(rawEntries) || rawEntries.length === 0) {
    throw new Error("Codex thread batch manifest must contain a non-empty entries array.");
  }

  const baseDirectory = path.dirname(resolvedPath);
  const entries = rawEntries.map((entry, index) =>
    normalizeBatchEntry(entry, index, defaults, baseDirectory)
  );

  return {
    path: resolvedPath,
    baseDirectory,
    defaults,
    entries
  };
}

export async function runCaptureCodexThreadBatch(command, runtime = {}) {
  const writer = runtime.writer || console;
  const runId = normalizeAuditRunId(command.runId);
  const manifest = runtime.manifest || loadCodexThreadBatchManifest(command.manifestPath);

  if (command.dryRun) {
    return previewCaptureCodexThreadBatch(command, manifest, writer);
  }

  const config = runtime.config || loadConfig();
  const captureFn = runtime.captureFn || captureCodexThreadToVault;
  const rebuildLinksFn = runtime.rebuildLinksFn || rebuildAutomaticLinks;
  const refreshViewsFn = runtime.refreshViewsFn || refreshWikiViews;
  const loadProviderFn = runtime.loadProviderFn || loadCodexLlmProvider;

  const willCompile = command.compile || manifest.entries.some((entry) => entry.compile === true);
  const provider =
    willCompile && !runtime.provider ? loadProviderFn() : runtime.provider || null;
  const templateContent =
    willCompile && !runtime.templateContent
      ? fs.readFileSync(path.join(config.projectRoot, "prompts", "compile-source.md"), "utf8")
      : runtime.templateContent || null;

  if (provider) {
    writer.log(`LLM provider: ${summarizeLlmProvider(provider)}`);
    writer.log(`Provider config: ${provider.configPath}`);
    writer.log("");
  }

  const successes = [];
  const failures = [];

  for (const entry of manifest.entries) {
    const effectiveCompile = entry.compile === true || (entry.compile == null && command.compile);
    writer.log(`=== CAPTURE: ${entry.title} ===`);
    try {
      const result = await captureFn(
        config,
        entry,
        {
          compile: effectiveCompile,
          runId,
          timeoutMs: command.timeoutMs,
          allowFilesystemFallback: true,
          preferCli: true,
          provider,
          templateContent,
          skipLinks: true,
          skipViews: true
        }
      );
      successes.push({
        entry,
        result
      });
      writer.log(`Captured raw note: ${result.ingestResult.path} (${result.ingestResult.mode})`);
      if (result.compileResult) {
        if (!result.compileResult.ok) {
          writer.log(`Compile failed: ${result.compileResult.error.message}`);
        } else {
          writer.log(`Compile endpoint: ${result.compileResult.response.endpoint}`);
          writer.log(`Compile log: ${result.compileResult.applyResult.logFile}`);
          for (const compileEntry of result.compileResult.applyResult.results) {
            if (compileEntry.path) {
              writer.log(`- ${compileEntry.action}: ${compileEntry.path} (${compileEntry.mode})`);
            }
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({
        entry,
        error: message
      });
      writer.error(`Capture failed: ${entry.title}`);
      writer.error(message);
      if (!command.continueOnError) {
        break;
      }
    }
    writer.log("");
  }

  let linkResult = null;
  let viewResults = [];
  if (successes.length > 0) {
    if (!command.skipLinks) {
      linkResult = rebuildLinksFn(config, {
        allowFilesystemFallback: true,
        preferCli: true
      });
      writer.log(
        `Rebuilt automatic links for ${linkResult.updated} note(s) out of ${linkResult.scanned} scanned.`
      );
    }
    if (!command.skipViews) {
      viewResults = refreshViewsFn(config, {
        allowFilesystemFallback: true,
        preferCli: true
      });
      writer.log(
        `Refreshed wiki views: ${viewResults.map((result) => `${result.path} (${result.mode})`).join(", ")}`
      );
    }
  }

  const summary = {
    dryRun: false,
    total: manifest.entries.length,
    completed: successes.length,
    failed: failures.length,
    failures,
    linkResult,
    viewResults,
    auditLogPath: ""
  };

  summary.auditLogPath = appendCodexThreadCaptureAuditLog(
    config.projectRoot,
    "capture-codex-thread-batch",
    {
      action: "capture-codex-thread-batch",
      run_id: runId,
      manifest_path: manifest.path,
      total: summary.total,
      completed: summary.completed,
      failed: summary.failed,
      compile_requested: command.compile === true,
      compiled_entries: successes.filter((entry) => entry.result.compileResult?.ok === true).length,
      entry_titles: manifest.entries.map((entry) => entry.title),
      raw_note_paths: successes.map((entry) => entry.result.ingestResult.path),
      failed_titles: failures.map((entry) => entry.entry.title),
      link_updated: summary.linkResult?.updated ?? 0,
      link_scanned: summary.linkResult?.scanned ?? 0,
      views_refreshed: Array.isArray(summary.viewResults) ? summary.viewResults.length : 0
    }
  );

  writer.log(
    `Batch summary: total=${summary.total}, completed=${summary.completed}, failed=${summary.failed}`
  );
  writer.log(`Batch audit log: ${summary.auditLogPath}`);

  return summary;
}

function printUsage(writer = console.error) {
  writer(
    "Usage: node scripts/capture-codex-thread-batch.mjs --manifest <path> [--compile] [--dry-run] [--skip-links] [--skip-views] [--continue-on-error|--fail-fast] [--timeout-ms N]"
  );
}

function previewCaptureCodexThreadBatch(command, manifest, writer) {
  writer.log(`Batch dry-run preview: total=${manifest.entries.length}`);
  for (const [index, entry] of manifest.entries.entries()) {
    const effectiveCompile = entry.compile === true || (entry.compile == null && command.compile);
    const thread = entry.threadUri || entry.threadId || "codex://threads/current-thread";
    writer.log(
      `${index + 1}. ${entry.title} topic=${entry.topic || "(none)"} thread=${thread} compile=${effectiveCompile}`
    );
  }
  writer.log("Dry-run only: no vault writes, provider calls, link rebuilds, view refreshes, or audit logs.");

  return {
    dryRun: true,
    total: manifest.entries.length,
    completed: 0,
    failed: 0,
    failures: [],
    linkResult: null,
    viewResults: [],
    auditLogPath: ""
  };
}

async function main(args = process.argv.slice(2)) {
  if (hasFlag(args, "help") || hasFlag(args, "h")) {
    printUsage(console.error);
    process.exit(0);
  }

  try {
    const command = parseCaptureCodexThreadBatchArgs(args);
    const summary = await runCaptureCodexThreadBatch(command);
    if (summary.failed > 0) {
      process.exit(1);
    }
  } catch (error) {
    printUsage(console.error);
    console.error("");
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

function normalizeBatchDefaults(value) {
  const source = value && typeof value === "object" ? value : {};
  return {
    sourceLabel: cleanText(source.sourceLabel ?? source.source_label),
    compile:
      typeof source.compile === "boolean"
        ? source.compile
        : null,
    status: cleanText(source.status),
    topic: cleanText(source.topic),
    capturedAt: cleanText(source.capturedAt ?? source.captured_at)
  };
}

function normalizeBatchEntry(value, index, defaults, baseDirectory) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Batch entry at index ${index} must be an object.`);
  }

  const body = cleanText(value.body);
  const bodyFile = cleanText(value.bodyFile ?? value.body_file);
  if (!body && !bodyFile) {
    throw new Error(`Batch entry at index ${index} must provide body or body_file.`);
  }

  return {
    threadUri: cleanText(value.threadUri ?? value.thread_uri),
    threadId: cleanText(value.threadId ?? value.thread_id),
    topic: cleanText(value.topic) || defaults.topic,
    title: cleanText(value.title),
    filenameBase: cleanText(value.filenameBase ?? value.filename_base) || null,
    body: body || resolveBodyFile(bodyFile, baseDirectory),
    sourceLabel: cleanText(value.sourceLabel ?? value.source_label) || defaults.sourceLabel,
    capturedAt: cleanText(value.capturedAt ?? value.captured_at) || defaults.capturedAt || null,
    status: cleanText(value.status) || defaults.status || "queued",
    compile:
      typeof value.compile === "boolean"
        ? value.compile
        : defaults.compile
  };
}

function resolveBodyFile(bodyFile, baseDirectory) {
  const resolvedPath = path.resolve(baseDirectory, bodyFile);
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Body file does not exist: ${resolvedPath}`);
  }
  return fs.readFileSync(resolvedPath, "utf8");
}

function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function stripUtf8Bom(text) {
  return String(text ?? "").replace(/^\uFEFF/, "");
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
