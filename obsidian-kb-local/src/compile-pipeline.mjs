import fs from "node:fs";
import path from "node:path";
import { assertWithinBoundary } from "./boundary.mjs";
import { findExistingByDedupKey, generateDedupKey } from "./dedup.mjs";
import {
  formatIso8601Tz,
  generateFrontmatter,
  parseFrontmatter,
  validateRawFrontmatter,
  validateWikiFrontmatter
} from "./frontmatter.mjs";
import { sanitizeFilename } from "./ingest.mjs";
import { extractHumanOverrides, mergeWithOverrides } from "./human-override.mjs";
import { writeNote } from "./note-writer.mjs";

const RAW_LANES = ["web", "papers", "repos", "manual", "articles"];
const WIKI_KIND_DIR_MAP = {
  concept: "concepts",
  entity: "entities",
  source: "sources",
  synthesis: "syntheses"
};

export function findRawNotes(vaultPath, machineRoot, options = {}) {
  const { topic = null, specificFile = null, onlyQueued = true } = options;

  if (specificFile) {
    assertWithinBoundary(specificFile, machineRoot);
    const fullPath = path.join(vaultPath, specificFile);
    if (!fs.existsSync(fullPath)) {
      throw new Error(`Raw note not found: ${specificFile}`);
    }

    const note = readVaultNote(vaultPath, fullPath);
    if (note.frontmatter?.kb_type !== "raw") {
      throw new Error(`Target file is not a raw note: ${specificFile}`);
    }

    if (onlyQueued && note.frontmatter.status !== "queued") {
      return [];
    }

    return [note];
  }

  const results = [];
  for (const lane of RAW_LANES) {
    const laneDir = path.join(vaultPath, machineRoot, "10-raw", lane);
    if (!fs.existsSync(laneDir)) {
      continue;
    }

    for (const filePath of walkMarkdownFiles(laneDir)) {
      const note = readVaultNote(vaultPath, filePath);
      if (note.frontmatter?.kb_type !== "raw") {
        continue;
      }

      if (onlyQueued && note.frontmatter.status !== "queued") {
        continue;
      }

      if (!matchesTopic(note.frontmatter.topic, topic)) {
        continue;
      }

      results.push(note);
    }
  }

  return results.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
}

export function findWikiNotes(vaultPath, machineRoot, options = {}) {
  const { topic = null } = options;
  const results = [];

  for (const directory of Object.values(WIKI_KIND_DIR_MAP)) {
    const wikiDir = path.join(vaultPath, machineRoot, "20-wiki", directory);
    if (!fs.existsSync(wikiDir)) {
      continue;
    }

    for (const filePath of walkMarkdownFiles(wikiDir)) {
      const note = readVaultNote(vaultPath, filePath);
      if (note.frontmatter?.kb_type !== "wiki") {
        continue;
      }

      if (!matchesTopic(note.frontmatter.topic, topic)) {
        continue;
      }

      results.push(note);
    }
  }

  return results.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
}

export function formatExistingWikiNotes(notes) {
  if (!notes || notes.length === 0) {
    return "(none)";
  }

  return notes
    .map((note) => {
      const compiledFrom = Array.isArray(note.frontmatter?.compiled_from)
        ? note.frontmatter.compiled_from.length
        : 0;
      return `- ${note.title} (${note.frontmatter?.wiki_kind || "unknown"}) [${note.relativePath}] compiled_from=${compiledFrom}`;
    })
    .join("\n");
}

export function buildCompilePrompt(templateContent, rawNote, existingWikiNotes) {
  const topic = rawNote.frontmatter?.topic || "";
  return templateContent
    .split("{{RAW_CONTENT}}")
    .join(rawNote.content)
    .split("{{TOPIC}}")
    .join(topic)
    .split("{{EXISTING_NOTES}}")
    .join(formatExistingWikiNotes(existingWikiNotes));
}

export function parseCompileNotes(input) {
  let parsed;
  try {
    parsed = JSON.parse(input);
  } catch (error) {
    throw new Error(`Failed to parse compile output JSON: ${error.message}`);
  }

  if (!Array.isArray(parsed)) {
    throw new Error("Compile output must be a JSON array");
  }

  return parsed.map((note, index) => normalizeCompileNote(note, index));
}

export function applyCompileOutput(config, params, options = {}) {
  const { rawPath, notes } = params ?? {};
  if (typeof rawPath !== "string" || rawPath.trim() === "") {
    throw new Error("applyCompileOutput requires rawPath");
  }

  if (!Array.isArray(notes)) {
    throw new Error("applyCompileOutput requires notes array");
  }

  assertWithinBoundary(rawPath, config.machineRoot);

  const rawFullPath = path.join(config.vaultPath, rawPath);
  if (!fs.existsSync(rawFullPath)) {
    throw new Error(`Raw note not found: ${rawPath}`);
  }

  const rawNote = readVaultNote(config.vaultPath, rawFullPath);
  validateRawFrontmatter(rawNote.frontmatter);

  const timestamp = options.timestamp || formatIso8601Tz(new Date());
  const today = timestamp.slice(0, 10);
  const logEntries = [];
  const results = [];

  for (const note of notes.map(normalizeCompileNoteFromInput(rawNote))) {
    if (note.action === "no_change") {
      results.push({
        action: "no_change",
        path: null,
        title: note.title
      });
      continue;
    }

    const wikiDirectory = WIKI_KIND_DIR_MAP[note.wiki_kind];
    if (!wikiDirectory) {
      throw new Error(`Unknown wiki_kind: ${note.wiki_kind}`);
    }

    const dedupReference = getDedupReference(note, rawNote);
    const dedupKey = generateDedupKey(note.topic, note.wiki_kind, dedupReference);
    const existingPath = findExistingByDedupKey(
      config.vaultPath,
      config.machineRoot,
      dedupKey
    );

    let notePath = existingPath;
    let finalBody = note.body;
    let compiledFrom = [rawPath];
    let reviewState = "draft";

    if (existingPath) {
      const existingFullPath = path.join(config.vaultPath, existingPath);
      const existingNote = readVaultNote(config.vaultPath, existingFullPath);
      const existingFrontmatter = existingNote.frontmatter ?? {};

      if (Array.isArray(existingFrontmatter.compiled_from)) {
        compiledFrom = uniqueStrings([...existingFrontmatter.compiled_from, rawPath]);
      }

      if (typeof existingFrontmatter.review_state === "string") {
        reviewState = existingFrontmatter.review_state;
      }

      finalBody = mergeWithOverrides(note.body, extractHumanOverrides(existingNote.content));
    } else {
      notePath = `${config.machineRoot}/20-wiki/${wikiDirectory}/${sanitizeFilename(note.title)}.md`;
      assertWithinBoundary(notePath, config.machineRoot);
    }

    const frontmatter = generateFrontmatter("wiki", {
      wiki_kind: note.wiki_kind,
      topic: note.topic,
      compiled_from: compiledFrom,
      compiled_at: timestamp,
      kb_date: today,
      review_state: reviewState,
      kb_source_count: compiledFrom.length,
      dedup_key: dedupKey
    });

    const content = `${frontmatter}\n\n# ${note.title}\n\n${finalBody.trim()}\n`;
    const writeResult = writeNote(
      config,
      { path: notePath, content },
      {
        allowFilesystemFallback: options.allowFilesystemFallback ?? true,
        preferCli: options.preferCli ?? true
      }
    );

    results.push({
      action: existingPath ? "update" : "create",
      path: notePath,
      title: note.title,
      mode: writeResult.mode,
      dedupKey
    });

    logEntries.push({
      timestamp,
      action: existingPath ? "update" : "create",
      path: notePath,
      raw_path: rawPath,
      dedup_key: dedupKey
    });
  }

  const rawStatus = results.some((entry) => entry.action !== "no_change")
    ? "compiled"
    : rawNote.frontmatter.status;

  const rawWriteResult = updateRawNoteStatus(
    config,
    rawPath,
    rawStatus,
    {
      allowFilesystemFallback: options.allowFilesystemFallback ?? true,
      preferCli: options.preferCli ?? true
    }
  );

  const logFile = appendCompileLog(config.projectRoot, today, logEntries);
  return {
    rawStatus,
    rawWriteMode: rawWriteResult.mode,
    logFile,
    results
  };
}

export function buildHealthCheckReport(config) {
  const rawNotes = scanLaneNotes(config.vaultPath, config.machineRoot, "10-raw", RAW_LANES);
  const wikiNotes = scanLaneNotes(
    config.vaultPath,
    config.machineRoot,
    "20-wiki",
    Object.values(WIKI_KIND_DIR_MAP)
  );

  const report = {
    orphan_wiki: [],
    stale_wiki: [],
    missing_source: [],
    contract_violations: [],
    dedup_conflicts: [],
    summary: ""
  };

  const newestRawByTopic = new Map();
  const existingRawPaths = new Set();

  for (const note of rawNotes) {
    if (note.frontmatter?.kb_type !== "raw") {
      report.contract_violations.push({
        path: note.relativePath,
        issue: "Raw lane note is missing kb_type: raw frontmatter",
        severity: "warning"
      });
      continue;
    }

    try {
      validateRawFrontmatter(note.frontmatter);
      existingRawPaths.add(note.relativePath);

      const capturedAt = Date.parse(note.frontmatter.captured_at);
      const topic = normalizeTopic(note.frontmatter.topic);
      const existing = newestRawByTopic.get(topic);
      if (!Number.isNaN(capturedAt) && (!existing || capturedAt > existing)) {
        newestRawByTopic.set(topic, capturedAt);
      }
    } catch (error) {
      report.contract_violations.push({
        path: note.relativePath,
        issue: error.message,
        severity: "warning"
      });
    }
  }

  const dedupMap = new Map();

  for (const note of wikiNotes) {
    if (note.frontmatter?.kb_type !== "wiki") {
      report.contract_violations.push({
        path: note.relativePath,
        issue: "Wiki lane note is missing kb_type: wiki frontmatter",
        severity: "warning"
      });
      continue;
    }

    try {
      validateWikiFrontmatter(note.frontmatter);
    } catch (error) {
      report.contract_violations.push({
        path: note.relativePath,
        issue: error.message,
        severity: "warning"
      });
      continue;
    }

    const compiledFrom = Array.isArray(note.frontmatter.compiled_from)
      ? note.frontmatter.compiled_from
      : [];

    if (compiledFrom.length === 0 && note.frontmatter.wiki_kind !== "synthesis") {
      report.orphan_wiki.push({
        path: note.relativePath,
        severity: "warning"
      });
    }

    for (const rawPath of compiledFrom) {
      if (!existingRawPaths.has(rawPath)) {
        report.missing_source.push({
          wiki_path: note.relativePath,
          missing_raw: rawPath,
          severity: "critical"
        });
      }
    }

    const topic = normalizeTopic(note.frontmatter.topic);
    const newestRaw = newestRawByTopic.get(topic);
    const compiledAt = Date.parse(note.frontmatter.compiled_at);
    if (
      newestRaw &&
      !Number.isNaN(compiledAt) &&
      compiledAt < newestRaw
    ) {
      report.stale_wiki.push({
        path: note.relativePath,
        newest_raw_at: new Date(newestRaw).toISOString(),
        compiled_at: note.frontmatter.compiled_at,
        severity: "info"
      });
    }

    const dedupKey = note.frontmatter.dedup_key;
    if (typeof dedupKey === "string" && dedupKey.trim() !== "") {
      const existingPaths = dedupMap.get(dedupKey) ?? [];
      existingPaths.push(note.relativePath);
      dedupMap.set(dedupKey, existingPaths);
    }
  }

  for (const [dedupKey, files] of dedupMap.entries()) {
    if (files.length > 1) {
      report.dedup_conflicts.push({
        dedup_key: dedupKey,
        files,
        severity: "critical"
      });
    }
  }

  const issueCount =
    report.orphan_wiki.length +
    report.stale_wiki.length +
    report.missing_source.length +
    report.contract_violations.length +
    report.dedup_conflicts.length;

  report.summary =
    issueCount === 0
      ? `Health check passed for ${rawNotes.length} raw notes and ${wikiNotes.length} wiki notes.`
      : `Health check found ${issueCount} issue(s) across ${rawNotes.length} raw notes and ${wikiNotes.length} wiki notes.`;

  return {
    rawNotes,
    wikiNotes,
    report
  };
}

export function updateRawNoteStatus(config, rawPath, status, options = {}) {
  assertWithinBoundary(rawPath, config.machineRoot);

  const fullPath = path.join(config.vaultPath, rawPath);
  if (!fs.existsSync(fullPath)) {
    throw new Error(`Raw note not found: ${rawPath}`);
  }

  const note = readVaultNote(config.vaultPath, fullPath);
  validateRawFrontmatter(note.frontmatter);

  const body = stripFrontmatter(note.content);
  const frontmatter = generateFrontmatter("raw", {
    source_type: note.frontmatter.source_type,
    topic: note.frontmatter.topic,
    source_url: note.frontmatter.source_url ?? "",
    captured_at: note.frontmatter.captured_at,
    kb_date: note.frontmatter.kb_date,
    status
  });

  const content = `${frontmatter}\n\n${body.trimStart()}`;
  return writeNote(
    config,
    { path: rawPath, content },
    {
      allowFilesystemFallback: options.allowFilesystemFallback ?? true,
      preferCli: options.preferCli ?? true
    }
  );
}

function appendCompileLog(projectRoot, today, entries) {
  const logDirectory = path.join(projectRoot, "logs");
  fs.mkdirSync(logDirectory, { recursive: true });

  const logFile = path.join(logDirectory, `compile-${today}.jsonl`);
  for (const entry of entries) {
    fs.appendFileSync(logFile, `${JSON.stringify(entry)}\n`, "utf8");
  }

  return logFile;
}

function scanLaneNotes(vaultPath, machineRoot, branchName, directories) {
  const results = [];
  for (const directory of directories) {
    const fullDirectory = path.join(vaultPath, machineRoot, branchName, directory);
    if (!fs.existsSync(fullDirectory)) {
      continue;
    }

    for (const filePath of walkMarkdownFiles(fullDirectory)) {
      results.push(readVaultNote(vaultPath, filePath));
    }
  }

  return results.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
}

function readVaultNote(vaultPath, fullPath) {
  const content = fs.readFileSync(fullPath, "utf8");
  return {
    fullPath,
    relativePath: path.relative(vaultPath, fullPath).replace(/\\/g, "/"),
    content,
    frontmatter: parseFrontmatter(content) ?? {},
    title: path.basename(fullPath, ".md")
  };
}

function walkMarkdownFiles(directory) {
  const results = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkMarkdownFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      results.push(fullPath);
    }
  }
  return results;
}

function stripFrontmatter(content) {
  return content.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "");
}

function matchesTopic(candidateTopic, requestedTopic) {
  if (!requestedTopic) {
    return true;
  }

  const candidate = String(candidateTopic ?? "").trim().toLowerCase();
  const requested = String(requestedTopic).trim().toLowerCase();
  return candidate.includes(requested);
}

function normalizeTopic(value) {
  return String(value ?? "").trim().toLowerCase();
}

function uniqueStrings(values) {
  return [...new Set(values.filter((value) => typeof value === "string" && value.trim() !== ""))];
}

function normalizeCompileNote(note, index) {
  if (!note || typeof note !== "object") {
    throw new Error(`Compile note at index ${index} must be an object`);
  }

  if (typeof note.wiki_kind !== "string" || note.wiki_kind.trim() === "") {
    throw new Error(`Compile note at index ${index} is missing wiki_kind`);
  }

  if (typeof note.title !== "string" || note.title.trim() === "") {
    throw new Error(`Compile note at index ${index} is missing title`);
  }

  if (typeof note.body !== "string") {
    throw new Error(`Compile note at index ${index} must include body`);
  }

  return {
    wiki_kind: note.wiki_kind.trim(),
    title: note.title.trim(),
    topic: typeof note.topic === "string" ? note.topic.trim() : "",
    body: note.body.trim(),
    source_url: typeof note.source_url === "string" ? note.source_url.trim() : "",
    action: typeof note.action === "string" ? note.action.trim() : ""
  };
}

function normalizeCompileNoteFromInput(rawNote) {
  return (note, index) => {
    const normalized = normalizeCompileNote(note, index);
    return {
      ...normalized,
      topic: normalized.topic || rawNote.frontmatter.topic || "",
      source_url: normalized.source_url || rawNote.frontmatter.source_url || ""
    };
  };
}

function getDedupReference(note, rawNote) {
  if (note.wiki_kind === "source") {
    return note.source_url || rawNote.frontmatter.source_url || rawNote.relativePath;
  }

  return `title:${sanitizeFilename(note.title).toLowerCase()}`;
}
