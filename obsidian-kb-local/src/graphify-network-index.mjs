import fs from "node:fs";
import path from "node:path";
import { getNetworkIndexPath, getNetworkTracePath } from "./view-paths.mjs";

export function buildSourceFileToVaultPathMap(manifest = {}) {
  const sourceMap = new Map();
  for (const note of Array.isArray(manifest.rawNotes) ? manifest.rawNotes : []) {
    const relativePath = normalizePath(note.relativePath);
    if (relativePath) {
      sourceMap.set(`raw/${path.posix.basename(relativePath)}`, relativePath);
    }
  }
  for (const note of Array.isArray(manifest.wikiNotes) ? manifest.wikiNotes : []) {
    const relativePath = normalizePath(note.relativePath);
    const kind = singularWikiKind(note.wikiKind || inferWikiKind(relativePath));
    if (relativePath) {
      sourceMap.set(`wiki/${kind}/${path.posix.basename(relativePath)}`, relativePath);
    }
  }
  return sourceMap;
}

export function buildGraphNetworkIndexNote(config, topic, paths) {
  const manifest = readJson(paths.manifestPath, {});
  const graph = readGraph(paths);
  const sourceMap = buildSourceFileToVaultPathMap(manifest);
  const nodeById = new Map(graph.nodes.map((node) => [String(node.id), node]));
  const bridgeRows = graph.links.map((link) => {
    const source = nodeById.get(String(link.source));
    const target = nodeById.get(String(link.target));
    return `- ${formatNodeLink(source, sourceMap)} -> ${formatNodeLink(target, sourceMap)} (${link.relation || "related"})`;
  });
  const communities = groupBy(graph.nodes, (node) => String(node.community ?? "unassigned"));
  const neighborhoodRows = [...communities.entries()].map(([community, nodes]) => {
    return `- Community ${community}: ${nodes.map((node) => formatNodeLink(node, sourceMap)).join(", ")}`;
  });

  return {
    path: getNetworkIndexPath(config.machineRoot, topic),
    content: [
      `# Network Index - ${topic}`,
      "",
      "## Layer 1: Bridge Links",
      "",
      bridgeRows.length > 0 ? bridgeRows.join("\n") : "- No bridge links yet.",
      "",
      "## Layer 2: Source Map",
      "",
      [...sourceMap.entries()].map(([sourceFile, vaultPath]) => `- \`${sourceFile}\` -> [[${vaultPath}|${path.posix.basename(vaultPath, ".md")}]]`).join("\n") || "- No staged sources.",
      "",
      "## Layer 3: Local Neighborhoods",
      "",
      neighborhoodRows.length > 0 ? neighborhoodRows.join("\n") : "- No local neighborhoods yet.",
      ""
    ].join("\n")
  };
}

export function buildGraphActivationTraceNote(config, topic, paths) {
  const manifest = readJson(paths.manifestPath, {});
  const graph = readGraph(paths);
  const sourceMap = buildSourceFileToVaultPathMap(manifest);
  const nodeById = new Map(graph.nodes.map((node) => [String(node.id), node]));
  const adjacency = new Map();
  for (const link of graph.links) {
    const list = adjacency.get(String(link.source)) || [];
    list.push(String(link.target));
    adjacency.set(String(link.source), list);
  }

  const twoHopRows = [];
  for (const first of graph.nodes) {
    for (const secondId of adjacency.get(String(first.id)) || []) {
      for (const thirdId of adjacency.get(secondId) || []) {
        twoHopRows.push(
          `- ${formatNodeLink(first, sourceMap)} -> ${formatNodeLink(nodeById.get(secondId), sourceMap)} -> ${formatNodeLink(nodeById.get(thirdId), sourceMap)}`
        );
      }
    }
  }

  return {
    path: getNetworkTracePath(config.machineRoot, topic),
    content: [
      `# Network Trace - ${topic}`,
      "",
      "## Seed Activation",
      "",
      graph.nodes.map((node) => `- ${formatNodeLink(node, sourceMap)}`).join("\n") || "- No seed nodes yet.",
      "",
      "## Two-hop spread",
      "",
      twoHopRows.length > 0 ? twoHopRows.join("\n") : "- No two-hop paths yet.",
      ""
    ].join("\n")
  };
}

function formatNodeLink(node, sourceMap) {
  if (!node) {
    return "(missing)";
  }
  const sourceFile = normalizePath(node.source_file);
  const vaultPath = sourceMap.get(sourceFile) || sourceFile;
  const label = String(node.label || path.posix.basename(vaultPath, ".md"));
  return vaultPath ? `[[${vaultPath}|${label}]]` : label;
}

function readGraph(paths) {
  const graph = readJson(path.join(paths.graphifyOutRoot, "graph.json"), { nodes: [], links: [] });
  return {
    nodes: Array.isArray(graph.nodes) ? graph.nodes : [],
    links: Array.isArray(graph.links) ? graph.links : []
  };
}

function groupBy(values, selector) {
  const groups = new Map();
  for (const value of values) {
    const key = selector(value);
    const group = groups.get(key) || [];
    group.push(value);
    groups.set(key, group);
  }
  return groups;
}

function inferWikiKind(relativePath) {
  const parts = normalizePath(relativePath).split("/");
  const index = parts.findIndex((part) => part === "20-wiki");
  return index >= 0 ? parts[index + 1] || "wiki" : "wiki";
}

function singularWikiKind(kind) {
  return String(kind || "wiki").replace(/s$/i, "").toLowerCase() || "wiki";
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
