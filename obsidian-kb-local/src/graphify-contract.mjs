import fs from "node:fs";
import path from "node:path";

const KNOWN_RELATIONS = new Set([
  "compiled_from",
  "conceptually_related_to",
  "cites",
  "references",
  "supports",
  "contrasts",
  "mentions"
]);

export function buildGraphContract(paths) {
  const manifest = readJson(paths.manifestPath, {});
  const graph = readJson(path.join(paths.graphifyOutRoot, "graph.json"), { nodes: [], links: [] });
  const extraction = readJson(path.join(paths.graphifyOutRoot, "markdown-extraction.json"), {});
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const links = Array.isArray(graph.links) ? graph.links : [];
  const communities = new Set(nodes.map((node) => node.community).filter((value) => value !== undefined && value !== null));
  const relationTypes = countBy(links, (link) => String(link.relation || "unknown"));
  const stagedFiles = buildStagedSourceFiles(manifest);
  const graphFiles = new Set(nodes.map((node) => normalizeGraphSource(node.source_file)).filter(Boolean));

  return {
    topic: String(manifest.topic || paths.topic || ""),
    selectionMode: String(manifest.selectionMode || ""),
    fallbackProfileId: String(manifest.fallbackProfileId || ""),
    manifest,
    graphCounts: {
      nodes: nodes.length,
      edges: links.length,
      communities: communities.size
    },
    extractionCounts: {
      nodes: Array.isArray(extraction.nodes) ? extraction.nodes.length : 0,
      edges: Array.isArray(extraction.edges) ? extraction.edges.length : 0
    },
    relationTypes: [...relationTypes.entries()].map(([name, count]) => ({ name, count })),
    manifestCoverage: {
      stagedFiles,
      missingStagedFiles: stagedFiles.filter((fileName) => !graphFiles.has(fileName))
    },
    queryRecipes: [
      { label: "Query topic", command: `node scripts/query-wiki.mjs --topic "${String(manifest.topic || "")}" --query "<question>"` },
      { label: "Refresh graph", command: `node scripts/graphify-refresh.mjs --topic "${String(manifest.topic || "")}"` },
      { label: "Inspect sidecar", command: `Get-ChildItem "${paths.graphifyOutRoot}"` }
    ]
  };
}

export function lintGraphArtifacts(paths, options = {}) {
  const contract = options.contract || buildGraphContract(paths);
  const graph = readJson(path.join(paths.graphifyOutRoot, "graph.json"), { nodes: [], links: [] });
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const links = Array.isArray(graph.links) ? graph.links : [];
  const nodeIds = new Set(nodes.map((node) => String(node.id || "")));
  const issues = [];

  for (const link of links) {
    if (!nodeIds.has(String(link.source || "")) || !nodeIds.has(String(link.target || ""))) {
      issues.push({ code: "edge-endpoint-not-found", severity: "error", edge: link });
    }
    if (!KNOWN_RELATIONS.has(String(link.relation || ""))) {
      issues.push({ code: "edge-unknown-relation", severity: "error", relation: String(link.relation || "") });
    }
    const confidenceScore = Number(link.confidence_score);
    if (Number.isFinite(confidenceScore) && (confidenceScore < 0 || confidenceScore > 1)) {
      issues.push({ code: "edge-confidence-score-out-of-range", severity: "warning", score: confidenceScore });
    }
  }

  if (contract.manifestCoverage.missingStagedFiles.length > 0) {
    issues.push({
      code: "missing-staged-graph-nodes",
      severity: "error",
      files: contract.manifestCoverage.missingStagedFiles
    });
  }

  const errorCount = issues.filter((issue) => issue.severity === "error").length;
  const warningCount = issues.filter((issue) => issue.severity === "warning").length;
  return {
    topic: contract.topic,
    status: errorCount > 0 ? "fail" : warningCount > 0 ? "warn" : "pass",
    errorCount,
    warningCount,
    issues
  };
}

export function buildGraphContractMarkdown(paths, options = {}) {
  const contract = options.contract || buildGraphContract(paths);
  const lint = options.lint || lintGraphArtifacts(paths, { contract });
  return [
    `# Graph Contract - ${contract.topic}`,
    "",
    "## Graph Contract",
    "",
    `- nodes: ${contract.graphCounts.nodes}`,
    `- edges: ${contract.graphCounts.edges}`,
    `- communities: ${contract.graphCounts.communities}`,
    `- lint: ${lint.status}`,
    "",
    "### Query Entry",
    "",
    ...contract.queryRecipes.map((recipe) => `- ${recipe.label}: \`${recipe.command}\``),
    ""
  ].join("\n");
}

export function writeGraphContractArtifacts(paths, options = {}) {
  const contract = options.contract || buildGraphContract(paths);
  const lint = options.lint || lintGraphArtifacts(paths, { contract });
  fs.mkdirSync(paths.graphifyOutRoot, { recursive: true });
  const contractPath = path.join(paths.graphifyOutRoot, "graph-contract.json");
  const lintPath = path.join(paths.graphifyOutRoot, "graph-lint.json");
  const markdownPath = path.join(paths.graphifyOutRoot, "GRAPH_CONTRACT.md");
  fs.writeFileSync(contractPath, JSON.stringify(contract, null, 2), "utf8");
  fs.writeFileSync(lintPath, JSON.stringify(lint, null, 2), "utf8");
  fs.writeFileSync(markdownPath, buildGraphContractMarkdown(paths, { contract, lint }), "utf8");
  return { contractPath, lintPath, markdownPath };
}

export function buildStagedSourceFiles(manifest = {}) {
  const rawFiles = normalizeArray(manifest.rawNotes).map((note) => `raw/${path.posix.basename(normalizePath(note.relativePath))}`);
  const wikiFiles = normalizeArray(manifest.wikiNotes).map((note) => {
    const kind = singularWikiKind(note.wikiKind || inferWikiKind(note.relativePath));
    return `wiki/${kind}/${path.posix.basename(normalizePath(note.relativePath))}`;
  });
  return [...rawFiles, ...wikiFiles].filter(Boolean);
}

function normalizeGraphSource(value) {
  return normalizePath(value).replace(/^\.?\//, "");
}

function inferWikiKind(relativePath) {
  const parts = normalizePath(relativePath).split("/");
  const index = parts.findIndex((part) => part === "20-wiki");
  return index >= 0 ? parts[index + 1] || "wiki" : "wiki";
}

function singularWikiKind(kind) {
  const normalized = String(kind || "wiki").replace(/s$/i, "").toLowerCase();
  return normalized || "wiki";
}

function countBy(values, selector) {
  const counts = new Map();
  for (const value of values) {
    const key = selector(value);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

function normalizeArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizePath(value) {
  return String(value || "").replace(/\\/g, "/");
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}
