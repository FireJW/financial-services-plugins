import fs from "node:fs";
import path from "node:path";
import { parseFrontmatter } from "./frontmatter.mjs";

export function generateDedupKey(topic, wikiKind, sourceUrl) {
  const normalizedTopic = (topic || "").trim().toLowerCase();
  const normalizedKind = (wikiKind || "").trim().toLowerCase();
  const normalizedUrl = (sourceUrl || "").trim().toLowerCase();

  if (!normalizedTopic) {
    throw new Error("generateDedupKey requires non-empty topic");
  }

  if (!normalizedKind) {
    throw new Error("generateDedupKey requires non-empty wikiKind");
  }

  return `${normalizedTopic}::${normalizedKind}::${normalizedUrl}`;
}

export function findExistingByDedupKey(vaultPath, machineRoot, dedupKey) {
  const wikiDirectory = path.join(vaultPath, machineRoot, "20-wiki");
  if (!fs.existsSync(wikiDirectory)) {
    return null;
  }

  const normalizedKey = String(dedupKey || "").trim().toLowerCase();

  for (const filePath of walkMarkdownFiles(wikiDirectory)) {
    const content = fs.readFileSync(filePath, "utf8");
    const frontmatter = parseFrontmatter(content);
    if (
      frontmatter &&
      typeof frontmatter.dedup_key === "string" &&
      frontmatter.dedup_key.trim().toLowerCase() === normalizedKey
    ) {
      return path.relative(vaultPath, filePath).replace(/\\/g, "/");
    }
  }

  return null;
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
