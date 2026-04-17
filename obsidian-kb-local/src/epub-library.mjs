import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { pathToFileURL } from "node:url";
import { formatIso8601Tz } from "./frontmatter.mjs";
import { ingestRawNote, sanitizeFilename } from "./ingest.mjs";

const DEFAULT_EPUB_ROOTS = ["D:\\下载", "D:\\桌面书单"];

export function getDefaultEpubRoots() {
  return [...DEFAULT_EPUB_ROOTS];
}

export function discoverEpubFiles(roots) {
  const results = [];
  const seen = new Set();

  for (const root of normalizeRoots(roots)) {
    walkEpubTree(root, results, seen);
  }

  return results.sort((left, right) => left.localeCompare(right));
}

export function loadEpubArtifacts(filePaths, options = {}) {
  const roots = normalizeRoots(options.roots);
  return filePaths.map((filePath) =>
    loadSingleEpubArtifact(filePath, {
      roots,
      machineRoot: options.machineRoot
    })
  );
}

export function deduplicateEpubArtifacts(artifacts) {
  const winners = new Map();

  for (const artifact of artifacts) {
    const dedupKey = normalizePathKey(artifact.realPath || artifact.filePath);
    if (!dedupKey) {
      continue;
    }

    const existing = winners.get(dedupKey);
    if (!existing || artifact.modifiedTimestamp > existing.modifiedTimestamp) {
      winners.set(dedupKey, artifact);
    }
  }

  return [...winners.values()].sort(
    (left, right) =>
      left.title.localeCompare(right.title) ||
      left.filePath.localeCompare(right.filePath)
  );
}

export function importEpubLibrary(config, artifacts, options = {}) {
  const results = [];
  const status = options.status || "archived";

  for (const artifact of artifacts) {
    const existed = fs.existsSync(path.join(config.vaultPath, artifact.notePath));
    const writeResult = ingestRawNote(
      config,
      {
        sourceType: "epub",
        topic: artifact.topic,
        sourceUrl: artifact.sourceUrl,
        title: artifact.title,
        filenameBase: artifact.filenameBase,
        body: formatEpubCorpusBody(artifact),
        capturedAt: artifact.capturedAt,
        status
      },
      {
        allowFilesystemFallback: options.allowFilesystemFallback ?? true,
        preferCli: options.preferCli ?? true
      }
    );

    results.push({
      action: existed ? "update" : "create",
      title: artifact.title,
      path: writeResult.path,
      mode: writeResult.mode,
      filePath: artifact.filePath
    });
  }

  return results;
}

export function formatEpubCorpusBody(artifact) {
  const lines = [
    "> Indexed from an external EPUB library. The original `.epub` stays at its current path and is not copied into the vault.",
    "",
    "## External File",
    "",
    `- Local path: ${artifact.filePath}`,
    `- File URI: ${artifact.sourceUrl}`,
    `- Source root: ${artifact.rootPath || "unknown"}`,
    `- Relative path: ${artifact.relativePath || path.basename(artifact.filePath)}`,
    `- File size: ${artifact.fileSizeLabel} (${artifact.fileSizeBytes} bytes)`,
    `- Last modified: ${artifact.modifiedAt}`,
    `- Indexed at: ${artifact.indexedAt}`,
    "",
    "## Book Metadata",
    "",
    `- Title: ${artifact.title}`,
    `- Topic: ${artifact.topic}`,
    `- Format: EPUB`,
    `- Access mode: external-path-reference`,
    "",
    "## Retrieval Notes",
    "",
    "- This note is a lightweight index entry, not a copied binary attachment.",
    "- Use the external file path when you need deeper reading, quote extraction, or chapter-level processing.",
    "- If this book becomes important, we can later add an on-demand extractor instead of copying the whole file.",
    "",
    "## Open Link",
    "",
    `[Open EPUB](${artifact.sourceUrl})`
  ];

  return `${lines.join("\n").trim()}\n`;
}

function loadSingleEpubArtifact(filePath, options = {}) {
  const resolved = path.resolve(filePath);
  const stat = fs.statSync(resolved);
  if (!stat.isFile() || path.extname(resolved).toLowerCase() !== ".epub") {
    throw new Error(`Unsupported EPUB target: ${resolved}`);
  }

  const realPath = resolveRealPath(resolved);
  const matchedRoot = findMatchedRoot(realPath, options.roots || []);
  const relativePath = matchedRoot
    ? path.relative(matchedRoot, realPath).replace(/\\/g, "/")
    : path.basename(realPath);
  const title = humanizeEpubTitle(realPath);
  const hash = shortHash(realPath);
  const filenameBase = `${sanitizeFilename(title).slice(0, 80)}--${hash}`;

  return {
    filePath: resolved,
    realPath,
    rootPath: matchedRoot,
    relativePath,
    title,
    topic: title,
    filenameBase,
    notePath: options.machineRoot
      ? `${options.machineRoot}/10-raw/books/${filenameBase}.md`
      : `10-raw/books/${filenameBase}.md`,
    sourceUrl: pathToFileURL(realPath).href,
    fileSizeBytes: stat.size,
    fileSizeLabel: formatFileSize(stat.size),
    modifiedAt: formatIso8601Tz(stat.mtime),
    modifiedTimestamp: stat.mtimeMs,
    capturedAt: formatIso8601Tz(stat.mtime),
    indexedAt: formatIso8601Tz(new Date())
  };
}

function walkEpubTree(rootPath, results, seen) {
  let entries = [];
  try {
    entries = fs.readdirSync(rootPath, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    const fullPath = path.join(rootPath, entry.name);
    if (entry.isSymbolicLink()) {
      continue;
    }

    if (entry.isDirectory()) {
      walkEpubTree(fullPath, results, seen);
      continue;
    }

    if (!entry.isFile() || path.extname(entry.name).toLowerCase() !== ".epub") {
      continue;
    }

    const key = normalizePathKey(resolveRealPath(fullPath));
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    results.push(path.resolve(fullPath));
  }
}

function normalizeRoots(roots) {
  return [...new Set((roots || []).map((root) => path.resolve(root)))];
}

function findMatchedRoot(filePath, roots) {
  const normalizedFilePath = normalizePathKey(filePath);
  return (
    roots.find((root) => {
      const normalizedRoot = normalizePathKey(root);
      return normalizedFilePath === normalizedRoot || normalizedFilePath.startsWith(`${normalizedRoot}\\`);
    }) || null
  );
}

function resolveRealPath(filePath) {
  try {
    return fs.realpathSync.native(filePath);
  } catch {
    return path.resolve(filePath);
  }
}

function normalizePathKey(filePath) {
  return path.resolve(String(filePath ?? "")).toLowerCase();
}

function humanizeEpubTitle(filePath) {
  const baseName = path.basename(filePath, path.extname(filePath));
  const title = baseName.replace(/[._]+/g, " ").replace(/\s+/g, " ").trim();
  return title || "Untitled EPUB";
}

function shortHash(input) {
  return crypto.createHash("sha1").update(String(input ?? "")).digest("hex").slice(0, 8);
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 1024) {
    return `${bytes || 0} B`;
  }

  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unitIndex]}`;
}
