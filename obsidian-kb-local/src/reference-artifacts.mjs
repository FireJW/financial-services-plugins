export function buildReferenceHubCompiledFrom(notes = []) {
  const paths = [];
  const seen = new Set();
  for (const note of notes) {
    const path = normalizeVaultPath(note?.path || note?.relativePath || note?.sourcePath);
    if (!path || !path.includes("/20-wiki/") || seen.has(path)) {
      continue;
    }
    seen.add(path);
    paths.push(path);
  }
  return paths;
}

export function extractLinkedWikiPathsFromSection(body = "", sectionTitle = "") {
  const section = extractMarkdownSection(body, sectionTitle);
  const paths = [];
  const seen = new Set();
  for (const match of section.matchAll(/\[\[([^\]|]+)(?:\|[^\]]*)?\]\]/g)) {
    const path = normalizeVaultPath(match[1]);
    if (!path || !path.includes("/20-wiki/")) {
      continue;
    }
    const markdownPath = path.endsWith(".md") ? path : `${path}.md`;
    if (!seen.has(markdownPath)) {
      seen.add(markdownPath);
      paths.push(markdownPath);
    }
  }
  return paths;
}

function extractMarkdownSection(body, sectionTitle) {
  const title = String(sectionTitle || "").trim().toLowerCase();
  if (!title) {
    return "";
  }

  const lines = String(body || "").split(/\r?\n/);
  const collected = [];
  let inSection = false;
  for (const line of lines) {
    const heading = line.match(/^##\s+(.+?)\s*$/);
    if (heading) {
      if (inSection) {
        break;
      }
      inSection = heading[1].trim().toLowerCase() === title;
      continue;
    }
    if (inSection) {
      collected.push(line);
    }
  }
  return collected.join("\n");
}

function normalizeVaultPath(value) {
  return String(value || "").trim().replace(/\\/g, "/");
}
