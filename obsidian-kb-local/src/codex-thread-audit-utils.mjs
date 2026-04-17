import fs from "node:fs";
import path from "node:path";

export const CODEX_THREAD_AUDIT_LOG_PATTERNS = {
  capture: /^capture-codex-thread-\d{4}-\d{2}-\d{2}\.jsonl$/,
  captureBatch: /^capture-codex-thread-batch-\d{4}-\d{2}-\d{2}\.jsonl$/,
  verify: /^verify-codex-thread-capture-\d{4}-\d{2}-\d{2}\.jsonl$/,
  reconcile: /^reconcile-codex-thread-capture-\d{4}-\d{2}-\d{2}\.jsonl$/
};

export function loadCodexThreadAuditLogs(projectRoot) {
  const logDirectory = path.join(projectRoot, "logs");
  return {
    logDirectory,
    capture: loadJsonlEntries(logDirectory, CODEX_THREAD_AUDIT_LOG_PATTERNS.capture),
    captureBatch: loadJsonlEntries(logDirectory, CODEX_THREAD_AUDIT_LOG_PATTERNS.captureBatch),
    verify: loadJsonlEntries(logDirectory, CODEX_THREAD_AUDIT_LOG_PATTERNS.verify),
    reconcile: loadJsonlEntries(logDirectory, CODEX_THREAD_AUDIT_LOG_PATTERNS.reconcile)
  };
}

export function isSyntheticAuditEntry(entry) {
  return entry?.synthetic === true;
}

export function sortDescendingByTimestamp(entries) {
  return (entries || []).slice().sort((left, right) =>
    String(right?.timestamp || "").localeCompare(String(left?.timestamp || ""))
  );
}

export function isArchivableAuditEntry(entry, cutoff) {
  const timestamp = new Date(String(entry?.timestamp || ""));
  if (!(timestamp instanceof Date) || Number.isNaN(timestamp.getTime()) || timestamp > cutoff) {
    return false;
  }

  if (isSyntheticAuditEntry(entry)) {
    return true;
  }

  const note = String(entry?.note || "").toLowerCase();
  if (note.includes("demo") || note.includes("validation")) {
    return true;
  }

  const tags = Array.isArray(entry?.tags) ? entry.tags.map((value) => String(value).toLowerCase()) : [];
  return tags.includes("demo") || tags.includes("synthetic");
}

export function loadJsonlEntries(directory, filePattern) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  const files = fs
    .readdirSync(directory)
    .filter((fileName) => filePattern.test(fileName))
    .sort()
    .map((fileName) => path.join(directory, fileName));

  const entries = [];
  for (const filePath of files) {
    const content = fs.readFileSync(filePath, "utf8");
    for (const line of content.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      try {
        entries.push(JSON.parse(trimmed));
      } catch {
        continue;
      }
    }
  }

  return entries;
}
