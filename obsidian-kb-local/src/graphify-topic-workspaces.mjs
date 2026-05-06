import fs from "node:fs";
import path from "node:path";

export function discoverGraphifyTopicWorkspaces(projectRoot) {
  const sidecarRoot = path.join(projectRoot, "graphify-sidecar");
  if (!fs.existsSync(sidecarRoot)) {
    return [];
  }

  return fs
    .readdirSync(sidecarRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("_"))
    .map((entry) => {
      const workspaceRoot = path.join(sidecarRoot, entry.name);
      const manifestPath = path.join(workspaceRoot, "manifest.json");
      const manifest = readJson(manifestPath, {});
      const topic = normalizeGraphifyTopicLabel(manifest.topic, manifest.slug || entry.name);
      return {
        root: workspaceRoot,
        sidecarRoot: workspaceRoot,
        manifestPath,
        graphifyOutRoot: path.join(workspaceRoot, "graphify-out"),
        slug: String(manifest.slug || entry.name),
        topic,
        selectionMode: String(manifest.selectionMode || "")
      };
    })
    .filter((workspace) => fs.existsSync(workspace.manifestPath))
    .sort((left, right) => left.topic.localeCompare(right.topic));
}

export function normalizeGraphifyTopicLabel(value, fallback = "untitled-note") {
  const cleaned = String(value || "")
    .replace(/^["'\s]+|["'\s]+$/g, "")
    .trim();
  if (!/[a-z0-9\u4e00-\u9fff]/i.test(cleaned)) {
    return String(fallback || "untitled-note").trim() || "untitled-note";
  }
  return cleaned;
}

export function readGraphifyWorkspaceStatus(workspace) {
  const root = typeof workspace === "string" ? workspace : workspace.root || workspace.sidecarRoot;
  const manifestPath = typeof workspace === "string" ? path.join(root, "manifest.json") : workspace.manifestPath;
  const graphifyOutRoot = typeof workspace === "string" ? path.join(root, "graphify-out") : workspace.graphifyOutRoot;
  const manifest = readJson(manifestPath, {});
  const contract = readJson(path.join(graphifyOutRoot, "graph-contract.json"), {});
  const lint = readJson(path.join(graphifyOutRoot, "graph-lint.json"), null);
  const graphPath = path.join(graphifyOutRoot, "graph.json");
  const topic = normalizeGraphifyTopicLabel(manifest.topic, manifest.slug || path.basename(root));
  const graphCounts = contract.graphCounts || {};

  if (!fs.existsSync(graphPath)) {
    return {
      topic,
      slug: String(manifest.slug || path.basename(root)),
      root,
      status: "missing-graph",
      nodes: 0,
      edges: 0,
      communities: 0,
      selectionMode: String(manifest.selectionMode || ""),
      warningCount: 0,
      errorCount: 0
    };
  }

  return {
    topic,
    slug: String(manifest.slug || path.basename(root)),
    root,
    status: String(lint?.status || "unknown"),
    nodes: Number(graphCounts.nodes || 0),
    edges: Number(graphCounts.edges || 0),
    communities: Number(graphCounts.communities || 0),
    selectionMode: String(contract.selectionMode || manifest.selectionMode || ""),
    warningCount: Number(lint?.warningCount || 0),
    errorCount: Number(lint?.errorCount || 0)
  };
}

export function loadGraphifyWorkspaceStatuses(projectRoot) {
  return discoverGraphifyTopicWorkspaces(projectRoot).map(readGraphifyWorkspaceStatus);
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}
