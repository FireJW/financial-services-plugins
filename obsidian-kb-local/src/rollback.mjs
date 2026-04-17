import fs from "node:fs";
import path from "node:path";
import { assertWithinBoundary } from "./boundary.mjs";
import { parseFrontmatter } from "./frontmatter.mjs";

const PROTECTED_PATTERNS = [
  /README\.md$/i,
  /KB Home\.md$/i,
  /\/contracts\//i,
  /\/manifests\//i,
  /\/migration\//i,
  /\/Runbooks\//i,
  /\.gitkeep$/i
];

export function isProtectedRollbackPath(relativePath) {
  return PROTECTED_PATTERNS.some((pattern) => pattern.test(relativePath));
}

export function collectRollbackCandidates(config, options = {}) {
  const topicFilter = String(options.topic || "").trim().toLowerCase();
  const kbRoot = path.join(config.vaultPath, config.machineRoot);
  if (!fs.existsSync(kbRoot)) {
    return [];
  }

  const candidates = [];
  for (const filePath of walkMarkdownFiles(kbRoot)) {
    const relativePath = path.relative(config.vaultPath, filePath).replace(/\\/g, "/");

    try {
      assertWithinBoundary(relativePath, config.machineRoot);
    } catch {
      continue;
    }

    if (isProtectedRollbackPath(relativePath)) {
      continue;
    }

    const content = fs.readFileSync(filePath, "utf8");
    const frontmatter = parseFrontmatter(content);
    if (!frontmatter || frontmatter.managed_by !== "codex") {
      continue;
    }

    if (topicFilter) {
      const noteTopic = String(frontmatter.topic || "").trim().toLowerCase();
      if (!noteTopic.includes(topicFilter)) {
        continue;
      }
    }

    candidates.push({
      fullPath: filePath,
      relativePath,
      kb_type: frontmatter.kb_type || "",
      wiki_kind: frontmatter.wiki_kind || "",
      topic: frontmatter.topic || "",
      managed_by: frontmatter.managed_by
    });
  }

  return candidates.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
}

export function writeRollbackLog(projectRoot, params) {
  const logDirectory = path.join(projectRoot, "logs");
  fs.mkdirSync(logDirectory, { recursive: true });

  const timestamp = params.timestamp || new Date().toISOString();
  const safeTimestamp = timestamp.replace(/[:.]/g, "-");
  const logFile = path.join(logDirectory, `rollback-${safeTimestamp}.json`);
  const logData = {
    timestamp,
    topic_filter: params.topic || null,
    files_deleted: params.candidates.map((candidate) => ({
      path: candidate.relativePath,
      kb_type: candidate.kb_type,
      topic: candidate.topic
    }))
  };

  fs.writeFileSync(logFile, JSON.stringify(logData, null, 2), "utf8");
  return logFile;
}

export function executeRollback(config, candidates) {
  let deleted = 0;
  for (const candidate of candidates) {
    assertWithinBoundary(candidate.relativePath, config.machineRoot);
    if (!fs.existsSync(candidate.fullPath)) {
      continue;
    }

    fs.unlinkSync(candidate.fullPath);
    deleted += 1;
  }

  cleanEmptyDirectories(path.join(config.vaultPath, config.machineRoot), config.machineRoot);
  return deleted;
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

function cleanEmptyDirectories(directory, machineRoot, rootDirectory = directory) {
  if (!fs.existsSync(directory)) {
    return;
  }

  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (!entry.isDirectory()) {
      continue;
    }

    const fullPath = path.join(directory, entry.name);
    cleanEmptyDirectories(fullPath, machineRoot, rootDirectory);

    const relativePath = path.relative(rootDirectory, fullPath).replace(/\\/g, "/");
    if (relativePath === "") {
      continue;
    }

    const candidatePath = `${machineRoot}/${relativePath}`;
    assertWithinBoundary(candidatePath, machineRoot);

    if (fs.readdirSync(fullPath).length === 0) {
      fs.rmdirSync(fullPath);
    }
  }
}
