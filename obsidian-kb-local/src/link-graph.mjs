import fs from "node:fs";
import path from "node:path";
import { parseFrontmatter } from "./frontmatter.mjs";
import { writeNote } from "./note-writer.mjs";

const LINK_GRAPH_START = "<!-- codex-link-graph:start -->";
const LINK_GRAPH_END = "<!-- codex-link-graph:end -->";
const WIKI_DIRECTORIES = ["concepts", "entities", "sources", "syntheses"];
const RAW_LINK_DIRECTORIES = ["articles", "books"];
const LINKABLE_RAW_SOURCE_TYPES = new Set(["article", "epub"]);
const ENGLISH_STOPWORDS = new Set([
  "about",
  "after",
  "article",
  "articles",
  "because",
  "before",
  "between",
  "build",
  "built",
  "from",
  "into",
  "local",
  "note",
  "notes",
  "that",
  "their",
  "there",
  "these",
  "this",
  "through",
  "using",
  "with",
  "without"
]);

export function rebuildAutomaticLinks(config, options = {}) {
  const notes = collectLinkableNotes(config.vaultPath, config.machineRoot, options);
  const graph = buildRelatedGraph(notes, options);
  const results = [];

  for (const note of notes) {
    const related = graph.get(note.relativePath) ?? [];
    const updatedContent = applyRelatedSection(note.content, related);
    if (updatedContent === note.content) {
      continue;
    }

    const writeResult = writeNote(
      config,
      {
        path: note.relativePath,
        content: updatedContent
      },
      {
        allowFilesystemFallback: options.allowFilesystemFallback ?? true,
        preferCli: options.preferCli ?? true
      }
    );

    results.push({
      title: note.title,
      path: note.relativePath,
      relatedCount: related.length,
      mode: writeResult.mode
    });
  }

  return {
    scanned: notes.length,
    updated: results.length,
    results
  };
}

export function collectLinkableNotes(vaultPath, machineRoot, options = {}) {
  const results = [];
  const includeWiki = options.includeWiki !== false;
  const includeArticleCorpus = options.includeArticleCorpus !== false;

  if (includeArticleCorpus) {
    for (const directory of RAW_LINK_DIRECTORIES) {
      const rawRoot = path.join(vaultPath, machineRoot, "10-raw", directory);
      results.push(...readLinkableFiles(vaultPath, rawRoot));
    }
  }

  if (includeWiki) {
    for (const directory of WIKI_DIRECTORIES) {
      const wikiRoot = path.join(vaultPath, machineRoot, "20-wiki", directory);
      results.push(...readLinkableFiles(vaultPath, wikiRoot));
    }
  }

  return results
    .filter(isLinkableNote)
    .map((note) => ({
      ...note,
      body: stripFrontmatter(note.content),
      cleanBody: stripManagedSection(stripFrontmatter(note.content)),
      topic: normalizeText(note.frontmatter.topic),
      headings: extractHeadings(stripFrontmatter(note.content)),
      tokens: buildTokenSet(note)
    }))
    .sort((left, right) => left.relativePath.localeCompare(right.relativePath));
}

export function buildRelatedGraph(notes, options = {}) {
  const maxLinks = normalizePositiveInt(options.maxLinks, 8);
  const minScore = normalizePositiveInt(options.minScore, 4);
  const graph = new Map(notes.map((note) => [note.relativePath, []]));

  for (let index = 0; index < notes.length; index += 1) {
    for (let next = index + 1; next < notes.length; next += 1) {
      const left = notes[index];
      const right = notes[next];
      const score = pairScore(left, right);
      if (score < minScore) {
        continue;
      }

      graph.get(left.relativePath).push({ note: right, score });
      graph.get(right.relativePath).push({ note: left, score });
    }
  }

  for (const [key, related] of graph.entries()) {
    graph.set(
      key,
      related
        .sort(
          (left, right) =>
            right.score - left.score || left.note.title.localeCompare(right.note.title)
        )
        .slice(0, maxLinks)
    );
  }

  return graph;
}

export function applyRelatedSection(content, relatedEntries) {
  const relatedSection =
    relatedEntries.length === 0 ? "" : buildRelatedSection(relatedEntries);
  const normalized = String(content ?? "").replace(/\r\n/g, "\n");
  const replaced = replaceManagedSection(normalized, relatedSection);
  return ensureTrailingNewline(replaced);
}

function buildRelatedSection(relatedEntries) {
  const lines = [LINK_GRAPH_START, "## Related", ""];
  for (const entry of relatedEntries) {
    lines.push(`- ${toWikiLink(entry.note.relativePath, entry.note.title)}`);
  }
  lines.push("", LINK_GRAPH_END);
  return lines.join("\n");
}

function toWikiLink(relativePath, title) {
  return `[[${relativePath.replace(/\\/g, "/").replace(/\.md$/i, "")}|${title}]]`;
}

function replaceManagedSection(content, section) {
  const blockPattern = new RegExp(
    `${escapeRegExp(LINK_GRAPH_START)}[\\s\\S]*?${escapeRegExp(LINK_GRAPH_END)}\\n*`,
    "g"
  );
  const withoutExisting = content.replace(blockPattern, "").trimEnd();
  if (!section) {
    return withoutExisting;
  }
  return `${withoutExisting}\n\n${section}`;
}

function pairScore(left, right) {
  if (normalizeText(left.title) === normalizeText(right.title)) {
    return 0;
  }

  let score = 0;

  if (left.topic && left.topic === right.topic) {
    score += 6;
  }

  if (mentionsTitle(left.cleanBody, right.title)) {
    score += 5;
  }

  if (mentionsTitle(right.cleanBody, left.title)) {
    score += 5;
  }

  const sharedTokens = intersectionSize(left.tokens, right.tokens);
  score += Math.min(sharedTokens, 4);

  return score;
}

function mentionsTitle(body, title) {
  const cleanTitle = String(title ?? "").trim();
  if (cleanTitle.length < 2) {
    return false;
  }
  return String(body ?? "").includes(cleanTitle);
}

function intersectionSize(left, right) {
  let count = 0;
  for (const token of left) {
    if (right.has(token)) {
      count += 1;
    }
  }
  return count;
}

function buildTokenSet(note) {
  const pool =
    note.frontmatter.kb_type === "raw"
      ? [note.title, note.frontmatter.topic].join("\n")
      : [note.title, note.frontmatter.topic, ...extractHeadings(stripFrontmatter(note.content))].join("\n");
  const tokens = new Set();

  for (const word of String(pool ?? "").match(/[A-Za-z][A-Za-z0-9/-]{2,}/g) ?? []) {
    const normalized = normalizeText(word);
    if (!ENGLISH_STOPWORDS.has(normalized)) {
      tokens.add(normalized);
    }
  }

  for (const phrase of String(pool ?? "").match(/[\u4E00-\u9FFF]{2,24}/g) ?? []) {
    tokens.add(phrase);
  }

  return tokens;
}

function readLinkableFiles(vaultPath, directory) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  const results = [];
  for (const filePath of walkMarkdownFiles(directory)) {
    const content = fs.readFileSync(filePath, "utf8");
    const body = stripFrontmatter(content);
    results.push({
      fullPath: filePath,
      relativePath: path.relative(vaultPath, filePath).replace(/\\/g, "/"),
      content,
      frontmatter: parseFrontmatter(content) ?? {},
      title: extractTitle(body, path.basename(filePath, ".md"))
    });
  }

  return results;
}

function walkMarkdownFiles(directory) {
  let entries = [];
  try {
    entries = fs.readdirSync(directory, { withFileTypes: true });
  } catch {
    return [];
  }

  const results = [];
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkMarkdownFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      results.push(fullPath);
    }
  }

  return results;
}

function isLinkableNote(note) {
  if (note.frontmatter.kb_type === "wiki") {
    return true;
  }

  return (
    note.frontmatter.kb_type === "raw" &&
    LINKABLE_RAW_SOURCE_TYPES.has(normalizeText(note.frontmatter.source_type))
  );
}

function extractTitle(body, fallbackTitle) {
  const match = String(body ?? "").match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : fallbackTitle;
}

function extractHeadings(body) {
  return String(body ?? "")
    .split(/\r?\n/)
    .map((line) => line.match(/^##+\s+(.+)$/))
    .filter(Boolean)
    .map((match) => match[1].trim())
    .filter(Boolean);
}

function stripFrontmatter(content) {
  return String(content ?? "").replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "");
}

function stripManagedSection(content) {
  return String(content ?? "").replace(
    new RegExp(
      `${escapeRegExp(LINK_GRAPH_START)}[\\s\\S]*?${escapeRegExp(LINK_GRAPH_END)}\\n*`,
      "g"
    ),
    ""
  );
}

function normalizeText(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim().toLowerCase();
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function ensureTrailingNewline(content) {
  return content.endsWith("\n") ? content : `${content}\n`;
}

function normalizePositiveInt(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
