import path from "node:path";
import { generateFrontmatter } from "./frontmatter.mjs";
import { sanitizeFilename } from "./ingest.mjs";
import { writeNote } from "./note-writer.mjs";

const STOPWORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "how",
  "in",
  "is",
  "of",
  "the",
  "to",
  "what"
]);

const INTENT_EXPANSIONS = [
  {
    label: "monetary-liquidity",
    triggers: ["money", "supply"],
    terms: [
      "balance-sheet expansion",
      "central bank",
      "credit creation",
      "dealer balance sheets",
      "dealer of last resort",
      "fed liquidity",
      "liquidity backstops",
      "monetary hierarchy",
      "quantitative easing",
      "reserves"
    ]
  }
];

export function selectRelevantWikiNotes(notes = [], query = "", options = {}) {
  const limit = normalizePositiveInteger(options.limit, 8);
  const terms = tokenizeQuery(query);
  if (terms.length === 0) {
    return [];
  }

  const scored = notes.map((note) => scoreWikiNote(note, terms, query));
  applyGraphScores(scored);

  const candidates = scored
    .filter((entry) => entry.score > 0)
    .sort(compareScoredNotes);

  return diversifyByTopic(candidates, limit).map((entry) => ({
    note: entry.note,
    score: entry.score,
    excerpt: buildExcerpt(entry.note, terms, entry.expansionMatches),
    retrieval: {
      mode: buildRetrievalMode(entry),
      directScore: entry.directScore,
      graphScore: entry.graphScore,
      expansionScore: entry.expansionScore,
      rrfScore: entry.rrfScore,
      matchedTerms: entry.matchedTerms,
      expansionMatches: entry.expansionMatches,
      intentLabel: entry.intentLabel,
      directBasis: entry.directBasis,
      signals: entry.signals
    }
  }));
}

export function buildWikiQueryPrompt(template, params = {}) {
  const context = formatNoteContext(params.selectedNotes || []);
  return String(template || "")
    .replaceAll("{{QUERY}}", String(params.query || ""))
    .replaceAll("{{TOPIC}}", String(params.topic || ""))
    .replaceAll("{{NOTE_CONTEXT}}", context);
}

export function buildQuerySynthesisNote(config, params = {}) {
  const topic = cleanText(params.topic || params.query || "Wiki Query");
  const query = cleanText(params.query);
  const answer = cleanText(params.answer) || "## Answer\n\n(No answer provided.)";
  const selectedNotes = Array.isArray(params.selectedNotes) ? params.selectedNotes : [];
  const compiledFrom = [
    ...new Set(
      selectedNotes
        .map((entry) => normalizeVaultPath(entry.note?.relativePath || entry.note?.path))
        .filter(Boolean)
    )
  ];
  const timestamp = cleanText(params.timestamp) || new Date().toISOString().slice(0, 19) + "+08:00";
  const title = `Q&A ${topic}`;
  const notePath = path.posix.join(
    normalizeVaultPath(config.machineRoot || "08-ai-kb"),
    "20-wiki",
    "syntheses",
    `${sanitizeFilename(title)}.md`
  );
  const frontmatter = generateFrontmatter("wiki", {
    wiki_kind: "synthesis",
    topic,
    compiled_from: compiledFrom,
    compiled_at: timestamp,
    kb_source_count: compiledFrom.length,
    dedup_key: `${topic.toLowerCase()}::synthesis::query:${slugify(query || topic)}`
  });

  const sources = selectedNotes.map((entry) => {
    const notePath = normalizeVaultPath(entry.note?.relativePath || entry.note?.path);
    const linkPath = notePath.replace(/\.md$/i, "");
    const title = cleanText(entry.note?.title) || path.posix.basename(linkPath);
    return `- [[${linkPath}|${title}]]${entry.score != null ? ` (score: ${entry.score})` : ""}`;
  });

  const content = [
    frontmatter,
    "",
    `# ${title}`,
    "",
    "## Query",
    "",
    query,
    "",
    answer,
    "",
    "## Source Notes",
    "",
    sources.length > 0 ? sources.join("\n") : "- No source notes selected.",
    ""
  ].join("\n");

  return {
    path: notePath,
    content
  };
}

export function writeQuerySynthesisNote(config, params = {}, options = {}) {
  const note = buildQuerySynthesisNote(config, params);
  const writeResult = writeNote(config, note, {
    allowFilesystemFallback: options.allowFilesystemFallback ?? true,
    preferCli: options.preferCli ?? true
  });
  return {
    ...note,
    writeResult
  };
}

function scoreWikiNote(note, terms, query) {
  const title = cleanText(note.title);
  const topic = cleanText(note.frontmatter?.topic);
  const content = cleanText(note.content);
  const haystacks = {
    title: title.toLowerCase(),
    topic: topic.toLowerCase(),
    content: content.toLowerCase(),
    path: normalizeVaultPath(note.relativePath || note.path).toLowerCase()
  };
  const phrase = terms.join(" ");
  const matchedTerms = terms.filter((term) =>
    haystacks.title.includes(term) ||
    haystacks.topic.includes(term) ||
    haystacks.content.includes(term) ||
    haystacks.path.includes(term)
  );

  let directScore = 0;
  const signals = [];
  if (phrase && haystacks.title.includes(phrase)) {
    directScore += 80;
    signals.push("title:phrase");
  }
  if (phrase && haystacks.topic.includes(phrase)) {
    directScore += 64;
    signals.push("topic:phrase");
  }
  if (phrase && haystacks.content.includes(phrase)) {
    directScore += 48;
    signals.push("content:phrase");
  }

  for (const term of terms) {
    if (haystacks.title.includes(term)) {
      directScore += 16;
      signals.push(`title:${term}`);
    }
    if (haystacks.topic.includes(term)) {
      directScore += 12;
      signals.push(`topic:${term}`);
    }
    if (haystacks.content.includes(term)) {
      directScore += 4;
      signals.push(`content:${term}`);
    }
  }

  const expansion = scoreIntentExpansion(note, terms);
  const directBasis = directScore > 0 ? "term-match" : expansion.score > 0 ? "intent-expansion" : "";
  return {
    note,
    directScore,
    graphScore: 0,
    expansionScore: expansion.score,
    rrfScore: 0,
    matchedTerms,
    expansionMatches: expansion.matches,
    intentLabel: expansion.label,
    directBasis,
    signals,
    score: directScore + expansion.score
  };
}

function applyGraphScores(entries) {
  const directEntries = entries.filter((entry) => entry.directScore > 0 || entry.expansionScore > 0);
  for (const entry of entries) {
    for (const direct of directEntries) {
      if (entry === direct) {
        continue;
      }
      const sharedSources = intersect(
        normalizeArray(entry.note.frontmatter?.compiled_from),
        normalizeArray(direct.note.frontmatter?.compiled_from)
      );
      if (sharedSources.length > 0) {
        entry.graphScore += 10;
        entry.signals.push(`shared-source:${direct.note.title}`);
      }
      if (noteLinksTo(entry.note, direct.note) || noteLinksTo(direct.note, entry.note)) {
        entry.graphScore += 8;
        entry.signals.push(`linked:${direct.note.title}`);
      }
    }
    if (entry.graphScore > 0) {
      entry.rrfScore = 4;
    }
    entry.score = entry.directScore + entry.expansionScore + entry.graphScore + entry.rrfScore;
  }
}

function scoreIntentExpansion(note, terms) {
  const text = [note.title, note.frontmatter?.topic, note.content].join("\n").toLowerCase();
  for (const intent of INTENT_EXPANSIONS) {
    if (!intent.triggers.every((trigger) => terms.includes(trigger))) {
      continue;
    }
    const matches = intent.terms.filter((term) => text.includes(term));
    if (matches.length > 0) {
      return {
        label: intent.label,
        matches,
        score: 18 + matches.length * 4
      };
    }
  }
  return {
    label: "",
    matches: [],
    score: 0
  };
}

function diversifyByTopic(entries, limit) {
  const selected = [];
  const usedTopics = new Set();
  for (const entry of entries) {
    const topic = cleanText(entry.note.frontmatter?.topic) || cleanText(entry.note.title);
    if (usedTopics.has(topic) && entries.length - selected.length >= limit - selected.length) {
      continue;
    }
    selected.push(entry);
    usedTopics.add(topic);
    if (selected.length >= limit) {
      return selected;
    }
  }
  for (const entry of entries) {
    if (!selected.includes(entry)) {
      selected.push(entry);
      if (selected.length >= limit) {
        break;
      }
    }
  }
  return selected;
}

function compareScoredNotes(left, right) {
  return (
    right.score - left.score ||
    right.directScore - left.directScore ||
    cleanText(right.note.frontmatter?.kb_date).localeCompare(cleanText(left.note.frontmatter?.kb_date)) ||
    cleanText(left.note.title).localeCompare(cleanText(right.note.title))
  );
}

function buildRetrievalMode(entry) {
  const modes = [];
  if (entry.directScore > 0 || entry.expansionScore > 0) {
    modes.push("direct");
  }
  if (entry.graphScore > 0) {
    modes.push("graph");
  }
  return modes.join("+") || "none";
}

function buildExcerpt(note, terms, expansionMatches = []) {
  const lines = String(note.content || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const searchTerms = [...terms, ...expansionMatches];
  const matched = lines.find((line) => {
    const lowered = line.toLowerCase();
    return searchTerms.some((term) => lowered.includes(term));
  });
  return (matched || lines.find((line) => !line.startsWith("#")) || "").slice(0, 500);
}

function formatNoteContext(selectedNotes) {
  if (selectedNotes.length === 0) {
    return "No relevant wiki notes selected.";
  }
  return selectedNotes
    .map((entry, index) => {
      const note = entry.note || {};
      const frontmatter = note.frontmatter || {};
      const retrieval = entry.retrieval || {};
      const lines = [
        `### ${index + 1}. ${cleanText(note.title) || "Untitled"}`,
        `- path: ${normalizeVaultPath(note.relativePath || note.path)}`,
        `- kind: ${cleanText(frontmatter.wiki_kind) || "wiki"}`,
        `- topic: ${cleanText(frontmatter.topic)}`,
        `- kb_date: ${cleanText(frontmatter.kb_date)}`,
        `- score: ${entry.score ?? 0}`
      ];
      if (retrieval.mode) {
        lines.push(`- retrieval: ${retrieval.mode}`);
        if (Array.isArray(retrieval.matchedTerms) && retrieval.matchedTerms.length > 0) {
          lines.push(`- terms=${retrieval.matchedTerms.join(", ")}`);
        }
        if (Array.isArray(retrieval.signals) && retrieval.signals.length > 0) {
          lines.push(`- signals=${retrieval.signals.join("; ")}`);
        }
      }
      lines.push("");
      lines.push(entry.excerpt || "");
      return lines.join("\n");
    })
    .join("\n\n");
}

function noteLinksTo(source, target) {
  const targetPath = normalizeVaultPath(target.relativePath || target.path).replace(/\.md$/i, "");
  const targetTitle = cleanText(target.title);
  const content = String(source.content || "");
  return [...content.matchAll(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g)].some((match) => {
    const linkPath = normalizeVaultPath(match[1]).replace(/\.md$/i, "");
    const alias = cleanText(match[2]);
    return linkPath === targetPath || alias === targetTitle;
  });
}

function tokenizeQuery(query) {
  return [
    ...new Set(
      String(query || "")
        .toLowerCase()
        .replace(/[^a-z0-9\u4e00-\u9fff]+/g, " ")
        .split(/\s+/)
        .map((term) => term.trim())
        .filter((term) => term && !STOPWORDS.has(term) && term.length > 1)
    )
  ];
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.map(normalizeVaultPath).filter(Boolean) : [];
}

function intersect(left, right) {
  const rightSet = new Set(right);
  return left.filter((entry) => rightSet.has(entry));
}

function normalizeVaultPath(value) {
  return String(value || "").trim().replace(/\\/g, "/");
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function slugify(value) {
  return cleanText(value)
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-|-$/g, "");
}

function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}
