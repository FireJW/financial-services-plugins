import { pathToFileURL } from "node:url";
import { loadConfig } from "../src/config.mjs";
import {
  isSyntheticAuditEntry,
  loadCodexThreadAuditLogs,
  sortDescendingByTimestamp
} from "../src/codex-thread-audit-utils.mjs";

export function parseCodexThreadAuditReportArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  return {
    json: list.includes("--json")
  };
}

export function buildCodexThreadAuditReport(config) {
  const { capture, captureBatch, verify, reconcile } = loadCodexThreadAuditLogs(config.projectRoot);

  const visibleCaptureLogs = capture.filter((entry) => !isSyntheticAuditEntry(entry));
  const visibleCaptureBatchLogs = captureBatch.filter((entry) => !isSyntheticAuditEntry(entry));
  const visibleVerifyLogs = verify.filter((entry) => !isSyntheticAuditEntry(entry));
  const visibleReconcileLogs = reconcile.filter((entry) => !isSyntheticAuditEntry(entry));
  const latestCapture = sortDescendingByTimestamp(visibleCaptureLogs)[0] || null;
  const latestVerify = sortDescendingByTimestamp(visibleVerifyLogs)[0] || null;
  const latestReconcile = sortDescendingByTimestamp(visibleReconcileLogs)[0] || null;
  const pendingRecovery = sortDescendingByTimestamp(
    visibleReconcileLogs.filter((entry) => Number(entry.missing || 0) > 0)
  )[0] || null;

  return {
    generated_at: new Date().toISOString(),
    summary: {
      capture_events: visibleCaptureLogs.length,
      capture_batch_events: visibleCaptureBatchLogs.length,
      verify_events: visibleVerifyLogs.length,
      reconcile_events: visibleReconcileLogs.length,
      pending_recovery_runs: visibleReconcileLogs.filter((entry) => Number(entry.missing || 0) > 0).length
    },
    latest_capture: latestCapture,
    latest_verify: latestVerify,
    latest_reconcile: latestReconcile,
    pending_recovery: pendingRecovery
  };
}

export async function runCodexThreadAuditReport(args = process.argv.slice(2), runtime = {}) {
  const command = parseCodexThreadAuditReportArgs(args);
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const report = buildCodexThreadAuditReport(config);

  if (command.json) {
    writer.log(JSON.stringify(report, null, 2));
    return report;
  }

  writer.log("Codex Thread Audit Report");
  writer.log("");
  writer.log(
    `Summary: capture=${report.summary.capture_events}, batch=${report.summary.capture_batch_events}, verify=${report.summary.verify_events}, reconcile=${report.summary.reconcile_events}, pending_recovery=${report.summary.pending_recovery_runs}`
  );
  if (report.latest_capture) {
    writer.log(
      `Latest capture: ${report.latest_capture.timestamp} | ${report.latest_capture.thread_uri || "(unknown)"} | ${report.latest_capture.raw_status || "unknown"} | run=${report.latest_capture.run_id || "(n/a)"}`
    );
  }
  if (report.latest_verify) {
    writer.log(
      `Latest verify: ${report.latest_verify.timestamp} | captured=${report.latest_verify.captured || 0} | missing=${report.latest_verify.missing || 0} | run=${report.latest_verify.run_id || "(n/a)"}`
    );
  }
  if (report.latest_reconcile) {
    writer.log(
      `Latest reconcile: ${report.latest_reconcile.timestamp} | captured=${report.latest_reconcile.captured || 0} | missing=${report.latest_reconcile.missing || 0} | run=${report.latest_reconcile.run_id || "(n/a)"}`
    );
  }
  if (report.pending_recovery) {
    writer.log(`Pending recovery manifest: ${report.pending_recovery.manifest_path || "(unknown)"}`);
  } else {
    writer.log("Pending recovery manifest: none");
  }

  return report;
}

function printUsage(writer = console.error) {
  writer("Usage: node scripts/codex-thread-audit-report.mjs [--json]");
}

async function main(args = process.argv.slice(2)) {
  if (args.includes("--help") || args.includes("-h")) {
    printUsage(console.error);
    process.exit(0);
  }

  try {
    await runCodexThreadAuditReport(args);
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
