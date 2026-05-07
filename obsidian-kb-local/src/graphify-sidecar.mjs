import fs from "node:fs";
import path from "node:path";
import { findRawNotes, findWikiNotes } from "./compile-pipeline.mjs";
import { sanitizeFilename } from "./ingest.mjs";
import { getGraphInsightsPath } from "./view-paths.mjs";

const PROFILE_RULES = [
  {
    id: "momentum-trading",
    triggers: ["momentum", "trading"],
    positives: ["momentum", "trading", "breakout", "trend", "continuation", "relative strength", "risk control"],
    negatives: ["inflation", "federal reserve", "monetary policy", "central bank", "expectations"]
  },
  {
    id: "wyckoff",
    triggers: ["wyckoff"],
    positives: ["wyckoff", "supply", "demand", "accumulation", "distribution", "effort", "result"],
    negatives: []
  },
  {
    id: "trading-psychology",
    triggers: ["trading", "psychology"],
    positives: ["trading psychology", "mindset", "uncertainty", "probability", "journaling", "discipline", "fomo"],
    negatives: []
  },
  {
    id: "ai-knowledge-workflows",
    triggers: ["ai", "knowledge", "workflows"],
    positives: ["llm", "wiki", "obsidian", "workflow", "query", "writeback", "docs", "permission", "entrypoint"],
    negatives: ["investing workflows", "portfolio support", "markets"]
  }
];

export function buildGraphifyTopicPaths(projectRoot, topic) {
  const slug = sanitizeFilename(topic);
  const sidecarRoot = path.join(projectRoot, "graphify-sidecar", slug);
  const inputRoot = path.join(sidecarRoot, "input");
  const rawRoot = path.join(inputRoot, "raw");
  const wikiRoot = path.join(inputRoot, "wiki");
  const graphifyOutRoot = path.join(sidecarRoot, "graphify-out");

  return {
    topic,
    slug,
    sidecarRoot,
    inputRoot,
    rawRoot,
    wikiRoot,
    graphifyOutRoot,
    manifestPath: path.join(sidecarRoot, "manifest.json"),
    runbookPath: path.join(sidecarRoot, "RUNBOOK.md"),
    readmePath: path.join(sidecarRoot, "README.md")
  };
}

export function resetGraphifyTopicWorkspace(paths) {
  for (const target of [paths.rawRoot, paths.wikiRoot, paths.graphifyOutRoot]) {
    fs.rmSync(target, { recursive: true, force: true });
    fs.mkdirSync(target, { recursive: true });
  }
}

export function extractArtifactPathsFromMarkdown(content) {
  const results = [];
  for (const match of String(content || "").matchAll(/\bpath=([^|\r\n]+)/g)) {
    const artifactPath = match[1].trim();
    if (artifactPath && fs.existsSync(artifactPath)) {
      results.push(artifactPath);
    }
  }
  return [...new Set(results)];
}

export function stageGraphifyTopicCorpus(config, topic, options = {}) {
  const paths = buildGraphifyTopicPaths(config.projectRoot, topic);
  resetGraphifyTopicWorkspace(paths);

  let rawNotes = findRawNotes(config.vaultPath, config.machineRoot, {
    topic,
    onlyQueued: false
  });
  let wikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, { topic });
  let selectionMode = "exact-topic";
  let fallbackProfileId = "";

  if (rawNotes.length === 0 && wikiNotes.length === 0) {
    const fallback = selectTopicFallbackNotes(
      [
        ...findRawNotes(config.vaultPath, config.machineRoot, { onlyQueued: false }),
        ...findWikiNotes(config.vaultPath, config.machineRoot, {})
      ],
      topic,
      options
    );
    rawNotes = fallback.rawNotes;
    wikiNotes = fallback.wikiNotes;
    selectionMode = fallback.selectionMode;
    fallbackProfileId = fallback.fallbackProfileId;
  }

  const stagedRaw = rawNotes.map((note) => stageNote(paths.rawRoot, note));
  const stagedWiki = wikiNotes.map((note) => {
    const wikiKind = String(note.frontmatter?.wiki_kind || "wiki").trim() || "wiki";
    return stageNote(path.join(paths.wikiRoot, wikiKind), note, { wikiKind });
  });

  const staged = {
    topic,
    slug: paths.slug,
    selectionMode,
    fallbackProfileId,
    counts: {
      raw: stagedRaw.length,
      wiki: stagedWiki.length
    },
    rawNotes: stagedRaw,
    wikiNotes: stagedWiki
  };

  fs.mkdirSync(paths.sidecarRoot, { recursive: true });
  fs.writeFileSync(paths.manifestPath, JSON.stringify(staged, null, 2), "utf8");
  fs.writeFileSync(paths.runbookPath, buildGraphifyRunbook(staged, paths), "utf8");
  fs.writeFileSync(paths.readmePath, buildGraphifySidecarReadme(staged, paths), "utf8");

  return { paths, staged };
}

export function buildGraphifyVaultNote(config, topic, paths) {
  const notePath = getGraphInsightsPath(config.machineRoot, topic);
  return {
    path: notePath,
    content: [
      `# Graph Insights - ${topic}`,
      "",
      `Sidecar workspace: \`${paths.sidecarRoot}\``,
      `Graph output: \`${paths.graphifyOutRoot}\``,
      "",
      "## Artifacts",
      "",
      `- Manifest: \`${paths.manifestPath}\``,
      `- graphify-out: \`${paths.graphifyOutRoot}\``,
      ""
    ].join("\n")
  };
}

export function buildGraphifySidecarReadme(staged, paths) {
  return [
    `# Graphify Sidecar - ${staged.topic}`,
    "",
    `Selection mode: ${staged.selectionMode}`,
    staged.fallbackProfileId ? `Fallback profile: ${staged.fallbackProfileId}` : "",
    "",
    "## Staged Corpus",
    "",
    `- raw notes: ${staged.counts.raw}`,
    `- wiki notes: ${staged.counts.wiki}`,
    "",
    "## Suggested command",
    "",
    "```powershell",
    `graphify --input "${paths.inputRoot}" --output "${paths.graphifyOutRoot}"`,
    "```",
    ""
  ]
    .filter((line) => line !== "")
    .join("\n");
}

export function selectTopicFallbackNotes(notes = [], topic = "", options = {}) {
  const limit = normalizePositiveInteger(options.limit, 20);
  const scored = notes
    .map((note) => ({ note, ...scoreTopicSearchNote(note, topic) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || getNoteTitle(left.note).localeCompare(getNoteTitle(right.note)))
    .slice(0, limit);

  const profileId = identifyProfile(topic)?.id || "keyword-fallback";
  return {
    selectionMode: profileId === "keyword-fallback" ? "keyword-fallback" : "profile-whitelist",
    fallbackProfileId: profileId === "keyword-fallback" ? "" : profileId,
    rawNotes: scored.filter((entry) => entry.note.frontmatter?.kb_type === "raw").map((entry) => entry.note),
    wikiNotes: scored.filter((entry) => entry.note.frontmatter?.kb_type === "wiki").map((entry) => entry.note)
  };
}

export function scoreTopicSearchNote(note, topic) {
  const tokens = tokenize(topic);
  const text = [
    getNoteTitle(note),
    note.relativePath,
    note.frontmatter?.topic,
    note.content
  ]
    .join("\n")
    .toLowerCase();
  const matchedTokens = tokens.filter((token) => text.includes(token));
  const profile = identifyProfile(topic);

  if (profile) {
    if (profile.negatives.some((term) => text.includes(term))) {
      return { score: 0, matchedTokens };
    }
    const positiveMatches = profile.positives.filter((term) => text.includes(term));
    const hasTriggerCoverage = profile.triggers.every((trigger) => text.includes(trigger));
    const score = hasTriggerCoverage || positiveMatches.length >= 2 ? positiveMatches.length * 10 + matchedTokens.length : 0;
    return { score, matchedTokens };
  }

  const phrase = tokens.join(" ");
  let score = 0;
  if (phrase && text.includes(phrase)) {
    score += 25;
  }
  score += matchedTokens.length * 5;
  return { score, matchedTokens };
}

function stageNote(destinationRoot, note, extra = {}) {
  fs.mkdirSync(destinationRoot, { recursive: true });
  const sourcePath = note.fullPath || note.path;
  const destination = path.join(destinationRoot, path.basename(sourcePath || note.relativePath));
  fs.copyFileSync(sourcePath, destination);
  return {
    title: getNoteTitle(note),
    relativePath: normalizeVaultPath(note.relativePath),
    destination,
    topic: String(note.frontmatter?.topic || ""),
    ...extra
  };
}

function buildGraphifyRunbook(staged, paths) {
  return [
    `# Runbook - ${staged.topic}`,
    "",
    "1. Inspect `input/raw` and `input/wiki`.",
    "2. Run Graphify against the staged input directory.",
    "3. Place generated artifacts under `graphify-out`.",
    "",
    `Workspace: \`${paths.sidecarRoot}\``,
    ""
  ].join("\n");
}

function identifyProfile(topic) {
  const tokens = tokenize(topic);
  return PROFILE_RULES.find((rule) => rule.triggers.every((trigger) => tokens.includes(trigger))) || null;
}

function tokenize(value) {
  return [
    ...new Set(
      String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9\u4e00-\u9fff]+/g, " ")
        .split(/\s+/)
        .map((token) => token.trim())
        .filter((token) => token.length > 1)
    )
  ];
}

function getNoteTitle(note) {
  return String(note?.title || path.basename(String(note?.relativePath || note?.path || ""), ".md")).trim();
}

function normalizeVaultPath(value) {
  return String(value || "").replace(/\\/g, "/");
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
