const FINANCE_KEYWORDS = [
  "accounting",
  "bank",
  "banking",
  "bond",
  "capital",
  "cash flow",
  "credit",
  "currency",
  "economics",
  "finance",
  "financial",
  "inflation",
  "invest",
  "investment",
  "liquidity",
  "macro",
  "market",
  "money",
  "monetary",
  "portfolio",
  "stock",
  "trading",
  "valuation"
];

const DIGEST_NOISE_HEADINGS = new Set([
  "contents",
  "copyright",
  "copyright information",
  "table of contents",
  "toc"
]);

export function parseContainerRootfile(xml) {
  const match = String(xml || "").match(/<rootfile\b[^>]*\bfull-path=(["'])(.*?)\1/i);
  return match ? decodeXmlEntities(match[2]).trim() : "";
}

export function parseOpfPackage(xml) {
  const text = String(xml || "");
  const metadata = {
    title: readXmlTag(text, "dc:title"),
    creator: readXmlTag(text, "dc:creator"),
    publisher: readXmlTag(text, "dc:publisher"),
    language: readXmlTag(text, "dc:language"),
    identifier: readXmlTag(text, "dc:identifier"),
    description: readXmlTag(text, "dc:description")
  };

  const manifest = new Map();
  for (const item of text.matchAll(/<item\b([^>]*)\/?>/gi)) {
    const attributes = parseAttributes(item[1]);
    if (attributes.id) {
      manifest.set(attributes.id, attributes);
    }
  }

  const spine = [];
  for (const itemref of text.matchAll(/<itemref\b([^>]*)\/?>/gi)) {
    const attributes = parseAttributes(itemref[1]);
    if (attributes.idref && String(attributes.linear || "").toLowerCase() !== "no") {
      spine.push(attributes.idref);
    }
  }

  return {
    metadata,
    manifest,
    spine
  };
}

export function convertXhtmlToMarkdown(xhtml) {
  const blocks = [];
  const pendingChapterNumbers = [];
  const body = String(xhtml || "")
    .replace(/<script\b[\s\S]*?<\/script>/gi, "")
    .replace(/<style\b[\s\S]*?<\/style>/gi, "");

  for (const match of body.matchAll(/<(p|blockquote|li)\b([^>]*)>([\s\S]*?)<\/\1>/gi)) {
    const tagName = match[1].toLowerCase();
    const attributes = parseAttributes(match[2]);
    const className = String(attributes.class || "").toLowerCase();
    const content = normalizeInlineText(match[3]);
    if (!content) {
      continue;
    }

    if (tagName === "p" && /\bcn\b/.test(className)) {
      pendingChapterNumbers.push(content);
      continue;
    }

    if (tagName === "p" && /\bct\b/.test(className)) {
      const chapterNumber = pendingChapterNumbers.shift();
      blocks.push(`## ${[chapterNumber, content].filter(Boolean).join(" ")}`);
      continue;
    }

    if (tagName === "p" && /\b(h1|h2|chapter|title)\b/.test(className)) {
      blocks.push(`## ${content}`);
      continue;
    }

    if (tagName === "blockquote") {
      blocks.push(`> ${content}`);
      continue;
    }

    if (tagName === "li") {
      blocks.push(`- ${content}`);
      continue;
    }

    blocks.push(content);
  }

  return `${blocks.join("\n\n").trim()}\n`;
}

export function isFinanceRelatedBookCandidate(note = {}) {
  const directText = [
    note.title,
    note.frontmatter?.topic,
    note.sourcePath,
    note.sourceUrl,
    stripRelatedSections(note.body)
  ]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();

  return FINANCE_KEYWORDS.some((keyword) => directText.includes(keyword));
}

export function selectFinanceRelatedBookNotes(notes = []) {
  const winners = new Map();
  for (const note of notes) {
    if (!isFinanceRelatedBookCandidate(note)) {
      continue;
    }
    const key = normalizeBookKey(note.title || note.frontmatter?.topic || note.sourcePath);
    if (!key) {
      continue;
    }
    const existing = winners.get(key);
    if (!existing || scoreFinanceBookNote(note) > scoreFinanceBookNote(existing)) {
      winners.set(key, note);
    }
  }
  return [...winners.values()].sort((left, right) =>
    String(left.title || "").localeCompare(String(right.title || ""))
  );
}

export function buildEpubCompileDigest(rawNote = {}, options = {}) {
  const maxChars = normalizePositiveInteger(options.maxChars, 12000);
  const minExcerptChars = normalizePositiveInteger(options.minExcerptChars, 160);
  const maxExcerptChars =
    options.maxExcerptChars == null
      ? Math.max(800, Math.floor(maxChars / 4))
      : normalizePositiveInteger(options.maxExcerptChars, 800);
  const sections = parseDigestSections(rawNote.content || rawNote.body || "");
  const usableSections = sections.filter((section) => !isDigestNoiseHeading(section.title));
  const selectedSections = usableSections.length > 0 ? usableSections : [
    {
      title: cleanText(rawNote.title || rawNote.frontmatter?.topic || "Book Excerpt"),
      body: cleanText(rawNote.content || rawNote.body)
    }
  ];

  const header = [
    "## Compile Digest",
    "",
    rawNote.title ? `- Title: ${cleanText(rawNote.title)}` : "",
    rawNote.frontmatter?.topic ? `- Topic: ${cleanText(rawNote.frontmatter.topic)}` : "",
    rawNote.frontmatter?.source_url ? `- Source: ${cleanText(rawNote.frontmatter.source_url)}` : "",
    "",
    "## Section Excerpts",
    ""
  ].filter((line, index, list) => line || list[index - 1] !== "").join("\n");

  const excerptBudget = Math.max(
    40,
    Math.floor((maxChars - header.length - selectedSections.length * 45) / selectedSections.length)
  );
  let excerptChars = Math.min(maxExcerptChars, Math.max(40, excerptBudget));
  if (excerptChars >= minExcerptChars || maxChars > header.length + selectedSections.length * minExcerptChars) {
    excerptChars = Math.max(Math.min(excerptChars, maxExcerptChars), Math.min(minExcerptChars, excerptChars));
  }

  let digest = renderDigest(header, selectedSections, excerptChars);
  while (digest.length > maxChars && excerptChars > 40) {
    excerptChars = Math.max(40, Math.floor(excerptChars * 0.8));
    digest = renderDigest(header, selectedSections, excerptChars);
  }

  if (digest.length <= maxChars) {
    return digest;
  }

  return `${digest.slice(0, Math.max(0, maxChars - 24)).trimEnd()}\n\n[Digest truncated]\n`;
}

export function buildEpubCompilePromptVariants(rawNote = {}, options = {}) {
  const variants = Array.isArray(options.maxCharsVariants) && options.maxCharsVariants.length > 0
    ? options.maxCharsVariants
    : [12000, 8000, 6000];

  return variants.map((maxChars) => ({
    label: `epub-digest-${maxChars}`,
    maxChars,
    promptContent: buildEpubCompileDigest(rawNote, {
      ...options,
      maxChars
    })
  }));
}

function renderDigest(header, sections, excerptChars) {
  const lines = [header.trimEnd()];
  for (const section of sections) {
    const excerpt = excerptText(section.body, excerptChars);
    lines.push("");
    lines.push(`### ${section.title}`);
    lines.push("");
    lines.push(excerpt.text || "(No extractable text.)");
    if (excerpt.truncated) {
      lines.push("");
      lines.push("[Excerpt truncated]");
    }
  }
  return `${lines.join("\n").trimEnd()}\n`;
}

function parseDigestSections(content) {
  const extracted = extractMarkdownBody(content);
  const matches = [...extracted.matchAll(/^##\s+(.+?)\s*$/gm)];
  if (matches.length === 0) {
    return [
      {
        title: "Book Excerpt",
        body: cleanText(extracted)
      }
    ];
  }

  const sections = [];
  for (let index = 0; index < matches.length; index += 1) {
    const current = matches[index];
    const next = matches[index + 1];
    const start = current.index + current[0].length;
    const end = next ? next.index : extracted.length;
    const title = cleanText(current[1]);
    const body = cleanText(extracted.slice(start, end));
    if (title && body) {
      sections.push({ title, body });
    }
  }
  return sections;
}

function extractMarkdownBody(content) {
  const text = String(content || "");
  const marker = text.search(/^##\s+Extracted Markdown\s*$/m);
  if (marker === -1) {
    return text;
  }
  return text.slice(marker).replace(/^##\s+Extracted Markdown\s*$/m, "");
}

function excerptText(text, maxChars) {
  const normalized = cleanText(text).replace(/\s+/g, " ");
  if (normalized.length <= maxChars) {
    return {
      text: normalized,
      truncated: false
    };
  }
  return {
    text: normalized.slice(0, maxChars).trimEnd(),
    truncated: true
  };
}

function isDigestNoiseHeading(title) {
  return DIGEST_NOISE_HEADINGS.has(cleanText(title).toLowerCase());
}

function stripRelatedSections(body) {
  const lines = String(body || "").split(/\r?\n/);
  const kept = [];
  let skipping = false;
  for (const line of lines) {
    if (/^##\s+Related\b/i.test(line.trim())) {
      skipping = true;
      continue;
    }
    if (skipping && /^##\s+/.test(line.trim())) {
      skipping = false;
    }
    if (!skipping) {
      kept.push(line);
    }
  }
  return kept.join("\n");
}

function scoreFinanceBookNote(note) {
  let score = 0;
  if (note.hasExtractedMarkdown) {
    score += 100;
  }
  score += Math.min(String(note.body || "").length, 10000) / 1000;
  score += String(note.sourcePath || "").length > 0 ? 1 : 0;
  return score;
}

function normalizeBookKey(value) {
  return cleanText(value)
    .toLowerCase()
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, " ")
    .trim();
}

function readXmlTag(xml, tagName) {
  const escaped = tagName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = String(xml || "").match(new RegExp(`<${escaped}\\b[^>]*>([\\s\\S]*?)<\\/${escaped}>`, "i"));
  return match ? normalizeInlineText(match[1]) : "";
}

function parseAttributes(text) {
  const attributes = {};
  for (const match of String(text || "").matchAll(/([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(["'])(.*?)\2/g)) {
    attributes[match[1]] = decodeXmlEntities(match[3]);
  }
  return attributes;
}

function normalizeInlineText(value) {
  return decodeXmlEntities(
    String(value || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<[^>]+>/g, "")
  )
    .replace(/\s+/g, " ")
    .trim();
}

function decodeXmlEntities(value) {
  return String(value || "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&apos;/g, "'");
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}
