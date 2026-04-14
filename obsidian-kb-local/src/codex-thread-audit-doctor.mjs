import fs from "node:fs";
import path from "node:path";
import { findRawNotes, findWikiNotes } from "./compile-pipeline.mjs";
import {
  isArchivableAuditEntry,
  isSyntheticAuditEntry,
  loadCodexThreadAuditLogs
} from "./codex-thread-audit-utils.mjs";

const DEFAULT_STALE_SYNTHETIC_DAYS = 7;

export function buildCodexThreadAuditDoctorReport(config, options = {}) {
  const now = options.now || new Date();
  const staleSyntheticDays =
    Number.isFinite(options.staleSyntheticDays) && options.staleSyntheticDays >= 0
      ? options.staleSyntheticDays
      : DEFAULT_STALE_SYNTHETIC_DAYS;
  const cutoff = new Date(now.getTime() - staleSyntheticDays * 24 * 60 * 60 * 1000);
  const logs = loadCodexThreadAuditLogs(config.projectRoot);
  const rawNotes = findRawNotes(config.vaultPath, config.machineRoot, {
    onlyQueued: false
  });
  const wikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {});
  const rawPaths = new Set(rawNotes.map((note) => note.relativePath));
  const compiledFromRawPaths = new Set(
    wikiNotes.flatMap((note) => (Array.isArray(note.frontmatter?.compiled_from) ? note.frontmatter.compiled_from : []))
  );

  const visibleEntries = [
    ...logs.capture,
    ...logs.captureBatch,
    ...logs.verify,
    ...logs.reconcile
  ].filter((entry) => !isSyntheticAuditEntry(entry));

  const checks = [
    buildMissingRunIdCheck(visibleEntries),
    buildPendingRecoveryManifestCheck(logs.reconcile),
    buildPendingRecoveryReportCheck(logs.reconcile),
    buildPendingRecoveryOutputCheck(logs.reconcile),
    buildCaptureRawExistsCheck(logs.capture, rawPaths),
    buildCompiledCaptureCoverageCheck(logs.capture, compiledFromRawPaths),
    buildStaleSyntheticCheck([...logs.capture, ...logs.captureBatch, ...logs.verify, ...logs.reconcile], cutoff, staleSyntheticDays)
  ];

  const failCount = checks.filter((check) => check.status === "fail").length;
  const warnCount = checks.filter((check) => check.status === "warn").length;
  const status = failCount > 0 ? "fail" : warnCount > 0 ? "warn" : "ok";

  return {
    generated_at: now.toISOString(),
    stale_synthetic_days: staleSyntheticDays,
    status,
    fail_count: failCount,
    warn_count: warnCount,
    checks
  };
}

function buildMissingRunIdCheck(entries) {
  const offenders = entries.filter((entry) => !String(entry?.run_id || "").trim());
  return {
    id: "missing-run-id",
    status: offenders.length > 0 ? "warn" : "ok",
    summary: offenders.length > 0 ? `${offenders.length} audit entries are missing run_id` : "All visible audit entries include run_id",
    count: offenders.length,
    samples: offenders.slice(0, 5).map((entry) => ({
      timestamp: entry.timestamp || "",
      action: entry.action || ""
    }))
  };
}

function buildPendingRecoveryManifestCheck(entries) {
  const offenders = entries.filter(
    (entry) =>
      !isSyntheticAuditEntry(entry) &&
      Number(entry?.missing || 0) > 0 &&
      (!entry?.manifest_path || !fs.existsSync(String(entry.manifest_path)))
  );
  return {
    id: "pending-recovery-manifest-missing",
    status: offenders.length > 0 ? "fail" : "ok",
    summary: offenders.length > 0 ? `${offenders.length} pending recovery runs are missing manifests` : "All pending recovery runs have manifests",
    count: offenders.length,
    samples: offenders.slice(0, 5).map((entry) => ({
      timestamp: entry.timestamp || "",
      manifest_path: entry.manifest_path || ""
    }))
  };
}

function buildPendingRecoveryReportCheck(entries) {
  const offenders = entries.filter(
    (entry) =>
      !isSyntheticAuditEntry(entry) &&
      Number(entry?.missing || 0) > 0 &&
      (!entry?.report_path || !fs.existsSync(String(entry.report_path)))
  );
  return {
    id: "pending-recovery-report-missing",
    status: offenders.length > 0 ? "fail" : "ok",
    summary: offenders.length > 0 ? `${offenders.length} pending recovery runs are missing reports` : "All pending recovery runs have reports",
    count: offenders.length,
    samples: offenders.slice(0, 5).map((entry) => ({
      timestamp: entry.timestamp || "",
      report_path: entry.report_path || ""
    }))
  };
}

function buildPendingRecoveryOutputCheck(entries) {
  const offenders = entries.filter(
    (entry) =>
      !isSyntheticAuditEntry(entry) &&
      Number(entry?.missing || 0) > 0 &&
      (!entry?.output_dir || !fs.existsSync(String(entry.output_dir)))
  );
  return {
    id: "pending-recovery-output-missing",
    status: offenders.length > 0 ? "warn" : "ok",
    summary: offenders.length > 0 ? `${offenders.length} pending recovery runs point to missing output directories` : "All pending recovery runs have output directories",
    count: offenders.length,
    samples: offenders.slice(0, 5).map((entry) => ({
      timestamp: entry.timestamp || "",
      output_dir: entry.output_dir || ""
    }))
  };
}

function buildCaptureRawExistsCheck(entries, rawPaths) {
  const offenders = entries.filter(
    (entry) =>
      !isSyntheticAuditEntry(entry) &&
      String(entry?.raw_note_path || "").trim() !== "" &&
      !rawPaths.has(String(entry.raw_note_path))
  );
  return {
    id: "capture-raw-note-missing",
    status: offenders.length > 0 ? "fail" : "ok",
    summary: offenders.length > 0 ? `${offenders.length} capture logs point to missing raw notes` : "All capture logs point to existing raw notes",
    count: offenders.length,
    samples: offenders.slice(0, 5).map((entry) => ({
      timestamp: entry.timestamp || "",
      raw_note_path: entry.raw_note_path || ""
    }))
  };
}

function buildCompiledCaptureCoverageCheck(entries, compiledFromRawPaths) {
  const offenders = entries.filter(
    (entry) =>
      !isSyntheticAuditEntry(entry) &&
      String(entry?.raw_status || "") === "compiled" &&
      String(entry?.raw_note_path || "").trim() !== "" &&
      !compiledFromRawPaths.has(String(entry.raw_note_path))
  );
  return {
    id: "compiled-capture-without-wiki",
    status: offenders.length > 0 ? "warn" : "ok",
    summary: offenders.length > 0 ? `${offenders.length} compiled captures have no derived wiki references` : "All compiled captures have derived wiki references",
    count: offenders.length,
    samples: offenders.slice(0, 5).map((entry) => ({
      timestamp: entry.timestamp || "",
      raw_note_path: entry.raw_note_path || ""
    }))
  };
}

function buildStaleSyntheticCheck(entries, cutoff, staleSyntheticDays) {
  const offenders = entries.filter((entry) => isArchivableAuditEntry(entry, cutoff));
  return {
    id: "stale-synthetic-audit-entries",
    status: offenders.length > 0 ? "warn" : "ok",
    summary:
      offenders.length > 0
        ? `${offenders.length} synthetic/demo audit entries are ready to archive (> ${staleSyntheticDays} days)`
        : "No stale synthetic/demo audit entries are waiting for archive",
    count: offenders.length,
    samples: offenders.slice(0, 5).map((entry) => ({
      timestamp: entry.timestamp || "",
      action: entry.action || "",
      note: entry.note || ""
    }))
  };
}
