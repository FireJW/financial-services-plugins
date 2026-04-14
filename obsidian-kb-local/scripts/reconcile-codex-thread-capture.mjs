import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { normalizeCodexThreadUri } from "../src/codex-thread-capture.mjs";
import {
  appendCodexThreadCaptureAuditLog,
  normalizeAuditRunId
} from "../src/codex-thread-capture-log.mjs";
import { loadConfig } from "../src/config.mjs";
import { loadCodexThreadBatchManifest } from "./capture-codex-thread-batch.mjs";
import {
  buildCodexThreadBodyTemplate,
  buildCodexThreadBatchInitPlan,
  collectCodexThreadRefs,
  parseInitCodexThreadBatchArgs
} from "./init-codex-thread-batch.mjs";
import {
  collectVerifyThreadUris,
  parseVerifyCodexThreadCaptureArgs,
  verifyCodexThreadCapture
} from "./verify-codex-thread-capture.mjs";

export function parseReconcileCodexThreadCaptureArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const outputDir = String(getArg(list, "output-dir") || "").trim();
  const topic = String(getArg(list, "topic") || "").trim();
  const titlePrefix = String(getArg(list, "title-prefix") || "Codex thread").trim();
  const sourceLabel = String(getArg(list, "source-label") || "Codex reconciliation").trim();
  const runId = String(getArg(list, "run-id") || "").trim();
  const compile = hasFlag(list, "no-compile") ? false : true;
  const json = hasFlag(list, "json");

  if (!outputDir) {
    throw new Error("Missing required --output-dir argument.");
  }

  const verify = parseVerifyCodexThreadCaptureArgs(args);
  return {
    ...verify,
    outputDir: path.resolve(outputDir),
    topic,
    titlePrefix,
    sourceLabel,
    runId,
    compile,
    json
  };
}

export function buildReconcileCodexThreadCapturePlan(config, command) {
  const verifyThreadUris = collectVerifyThreadUris(command);
  const verifyResults = verifyCodexThreadCapture(config, verifyThreadUris);
  const missingUris = verifyResults.filter((entry) => !entry.ok).map((entry) => entry.threadUri);

  const report = {
    generated_at: new Date().toISOString(),
    total: verifyResults.length,
    captured: verifyResults.filter((entry) => entry.ok).length,
    missing: missingUris.length,
    results: verifyResults
  };

  const outputDir = command.outputDir;
  const manifestPath = path.join(outputDir, "missing-manifest.json");
  const reportPath = path.join(outputDir, "verification-report.json");
  const bodiesDirectory = path.join(outputDir, "bodies");

  let batchManifest = {
    defaults: {
      source_label: command.sourceLabel,
      compile: command.compile,
      status: "queued"
    },
    entries: []
  };
  let bodyFiles = [];

  if (missingUris.length > 0) {
    if (command.manifestPath) {
      const sourceManifest = loadCodexThreadBatchManifest(command.manifestPath);
      const missingEntries = sourceManifest.entries.filter((entry) =>
        missingUris.includes(normalizeCodexThreadUri(entry.threadUri, entry.threadId))
      );
      const built = buildMissingManifestFromExistingEntries(
        missingEntries,
        outputDir,
        {
          sourceLabel: command.sourceLabel,
          compile: command.compile
        }
      );
      batchManifest = built.manifest;
      bodyFiles = built.bodyFiles;
    } else {
      const plan = buildCodexThreadBatchInitPlan({
        outputDir,
        threadsFile: "",
        threadUris: missingUris,
        threadIds: [],
        topic: command.topic,
        titlePrefix: command.titlePrefix,
        sourceLabel: command.sourceLabel,
        compile: command.compile
      });
      batchManifest = plan.manifest;
      bodyFiles = plan.entries.map((entry) => ({
        path: entry.bodyPath,
        content: buildCodexThreadBodyTemplate(entry)
      }));
    }
  }

  return {
    outputDir,
    report,
    reportPath,
    manifestPath,
    bodiesDirectory,
    batchManifest,
    bodyFiles
  };
}

export function writeReconcileCodexThreadCapturePlan(plan) {
  fs.mkdirSync(plan.outputDir, { recursive: true });
  fs.mkdirSync(plan.bodiesDirectory, { recursive: true });
  fs.writeFileSync(plan.reportPath, `${JSON.stringify(plan.report, null, 2)}\n`, "utf8");
  fs.writeFileSync(plan.manifestPath, `${JSON.stringify(plan.batchManifest, null, 2)}\n`, "utf8");

  for (const file of plan.bodyFiles) {
    fs.mkdirSync(path.dirname(file.path), { recursive: true });
    if (!fs.existsSync(file.path)) {
      fs.writeFileSync(file.path, file.content, "utf8");
    }
  }

  return plan;
}

export async function runReconcileCodexThreadCapture(args = process.argv.slice(2), runtime = {}) {
  const command = parseReconcileCodexThreadCaptureArgs(args);
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const runId = normalizeAuditRunId(command.runId);
  const plan = buildReconcileCodexThreadCapturePlan(config, command);
  writeReconcileCodexThreadCapturePlan(plan);

  appendCodexThreadCaptureAuditLog(config.projectRoot, "reconcile-codex-thread-capture", {
    action: "reconcile-codex-thread-capture",
    run_id: runId,
    total: plan.report.total,
    captured: plan.report.captured,
    missing: plan.report.missing,
    output_dir: plan.outputDir,
    report_path: plan.reportPath,
    manifest_path: plan.manifestPath,
    body_file_count: plan.bodyFiles.length,
    missing_thread_uris: plan.report.results
      .filter((entry) => !entry.ok)
      .map((entry) => entry.threadUri)
  });

  if (command.json) {
    writer.log(
      JSON.stringify(
        {
          reportPath: plan.reportPath,
          manifestPath: plan.manifestPath,
          bodyFiles: plan.bodyFiles.map((entry) => entry.path),
          summary: {
            total: plan.report.total,
            captured: plan.report.captured,
            missing: plan.report.missing
          }
        },
        null,
        2
      )
    );
    return plan;
  }

  writer.log(`Verification report: ${plan.reportPath}`);
  writer.log(`Missing manifest: ${plan.manifestPath}`);
  writer.log(
    `Summary: total=${plan.report.total}, captured=${plan.report.captured}, missing=${plan.report.missing}`
  );
  if (plan.bodyFiles.length > 0) {
    writer.log("Body files:");
    for (const file of plan.bodyFiles) {
      writer.log(`- ${file.path}`);
    }
  }

  return plan;
}

function printUsage(writer = console.error) {
  writer(
    "Usage: node scripts/reconcile-codex-thread-capture.mjs --output-dir <path> [--manifest <path> | --threads-file <path> | --thread-uri <codex://threads/...> | --thread-id <id>] [--topic <topic>] [--title-prefix <prefix>] [--source-label <label>] [--no-compile] [--json]"
  );
}

async function main(args = process.argv.slice(2)) {
  if (hasFlag(args, "help") || hasFlag(args, "h")) {
    printUsage(console.error);
    process.exit(0);
  }

  try {
    const plan = await runReconcileCodexThreadCapture(args);
    if (plan.report.missing > 0) {
      process.exit(1);
    }
  } catch (error) {
    printUsage(console.error);
    console.error("");
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

function buildMissingManifestFromExistingEntries(entries, outputDir, defaults) {
  const bodiesDirectory = path.join(outputDir, "bodies");
  const manifestEntries = [];
  const bodyFiles = [];

  for (const entry of entries) {
    const bodyFilename = `${sanitizeFilename(entry.title || "codex-thread")}.md`;
    const bodyPath = path.join(bodiesDirectory, bodyFilename);
    bodyFiles.push({
      path: bodyPath,
      content: String(entry.body || "").trim() || buildCodexThreadBodyTemplate({
        thread_uri: normalizeCodexThreadUri(entry.threadUri, entry.threadId)
      })
    });
    const manifestEntry = {
      thread_uri: normalizeCodexThreadUri(entry.threadUri, entry.threadId),
      topic: entry.topic || "",
      title: entry.title || "",
      body_file: path.posix.join("bodies", bodyFilename)
    };
    if (entry.compile !== defaults.compile && typeof entry.compile === "boolean") {
      manifestEntry.compile = entry.compile;
    }
    manifestEntries.push(manifestEntry);
  }

  return {
    manifest: {
      defaults: {
        source_label: defaults.sourceLabel,
        compile: defaults.compile,
        status: "queued"
      },
      entries: manifestEntries
    },
    bodyFiles
  };
}

function sanitizeFilename(value) {
  return String(value || "")
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 100);
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
