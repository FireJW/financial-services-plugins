import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { formatIso8601Tz } from "./frontmatter.mjs";

export function getCodexThreadCaptureLogDirectory(projectRoot) {
  return projectRoot ? path.join(projectRoot, "logs") : "";
}

export function getCodexThreadCaptureLogPath(projectRoot, logType, date = new Date()) {
  const logDirectory = getCodexThreadCaptureLogDirectory(projectRoot);
  if (!logDirectory) {
    return "";
  }

  return path.join(logDirectory, `${logType}-${formatDateStamp(date)}.jsonl`);
}

export function appendCodexThreadCaptureAuditLog(projectRoot, logType, entry, options = {}) {
  const logPath = getCodexThreadCaptureLogPath(projectRoot, logType, options.now || new Date());
  if (!logPath) {
    return "";
  }

  const timestamp = entry?.timestamp || formatIso8601Tz(options.now || new Date());
  const runId = normalizeAuditRunId(entry?.run_id, options.now || new Date());
  const payload = {
    timestamp,
    run_id: runId,
    ...entry
  };

  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.appendFileSync(logPath, `${JSON.stringify(payload)}\n`, "utf8");
  return logPath;
}

export function normalizeAuditRunId(runId, now = new Date()) {
  const explicit = String(runId || "").trim();
  if (explicit) {
    return explicit;
  }

  const stamp = formatDateStamp(now).replace(/-/g, "");
  const clock = formatClockStamp(now);
  const suffix = crypto.randomUUID().slice(0, 8);
  return `ctr-${stamp}T${clock}-${suffix}`;
}

export function buildBackfilledAuditRunId(entry, context = {}) {
  const timestamp = String(entry?.timestamp || "").trim();
  const action = sanitizeRunIdSegment(entry?.action || context.logType || "audit");
  const timeSegment = sanitizeRunIdTimestamp(timestamp) || "unknown";
  const ordinal = String((context.index ?? 0) + 1).padStart(3, "0");
  return `legacy-${timeSegment}-${action}-${ordinal}`;
}

function formatDateStamp(value) {
  const date = value instanceof Date ? value : new Date(value);
  const year = String(date.getFullYear());
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatClockStamp(value) {
  const date = value instanceof Date ? value : new Date(value);
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${hours}${minutes}${seconds}`;
}

function sanitizeRunIdTimestamp(value) {
  const normalized = String(value || "").replace(/[^0-9]/g, "");
  return normalized.slice(0, 14);
}

function sanitizeRunIdSegment(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 32) || "audit";
}
