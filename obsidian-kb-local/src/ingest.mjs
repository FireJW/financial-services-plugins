import path from "node:path";
import { assertWithinBoundary } from "./boundary.mjs";
import {
  generateFrontmatter,
  parseFrontmatter,
  validateRawFrontmatter
} from "./frontmatter.mjs";
import { writeNote } from "./note-writer.mjs";

const LANE_MAP = {
  web_article: "web",
  paper: "papers",
  repo: "repos",
  manual: "manual"
};

export function ingestRawNote(config, params, options = {}) {
  const {
    sourceType,
    topic,
    sourceUrl = "",
    title,
    body = ""
  } = params ?? {};

  if (typeof sourceType !== "string" || sourceType.trim() === "") {
    throw new Error("ingestRawNote requires sourceType");
  }

  if (typeof topic !== "string" || topic.trim() === "") {
    throw new Error("ingestRawNote requires topic");
  }

  if (typeof title !== "string" || title.trim() === "") {
    throw new Error("ingestRawNote requires title");
  }

  const lane = LANE_MAP[sourceType];
  if (!lane) {
    throw new Error(
      `Unknown sourceType: ${sourceType}. Must be one of: ${Object.keys(LANE_MAP).join(", ")}`
    );
  }

  const safeName = sanitizeFilename(title);
  const notePath = `${config.machineRoot}/10-raw/${lane}/${safeName}.md`;
  assertWithinBoundary(notePath, config.machineRoot);

  const frontmatter = generateFrontmatter("raw", {
    source_type: sourceType,
    topic: topic.trim(),
    source_url: sourceUrl.trim(),
    status: "queued"
  });

  validateRawFrontmatter(parseFrontmatter(`${frontmatter}\n`));

  const normalizedBody = normalizeBody(body);
  const content = [
    frontmatter,
    "",
    `# ${title.trim()}`,
    "",
    normalizedBody
  ].join("\n");

  return writeNote(
    config,
    { path: notePath, content },
    {
      allowFilesystemFallback: options.allowFilesystemFallback ?? true,
      preferCli: options.preferCli ?? true
    }
  );
}

export function sanitizeFilename(name) {
  const baseName = String(name ?? "").trim();
  const withoutInvalidCharacters = baseName
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 100);

  return withoutInvalidCharacters || "untitled-note";
}

function normalizeBody(body) {
  const normalized = String(body ?? "").replace(/\r\n/g, "\n").trim();
  return normalized || "## Summary\n\n(No content provided yet)";
}

export function getRawLanePath(machineRoot, sourceType, title) {
  const lane = LANE_MAP[sourceType];
  if (!lane) {
    throw new Error(
      `Unknown sourceType: ${sourceType}. Must be one of: ${Object.keys(LANE_MAP).join(", ")}`
    );
  }

  const relativePath = path.posix.join(
    machineRoot.replace(/\\/g, "/"),
    "10-raw",
    lane,
    `${sanitizeFilename(title)}.md`
  );

  assertWithinBoundary(relativePath, machineRoot);
  return relativePath;
}
