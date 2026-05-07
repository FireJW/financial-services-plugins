import fs from "node:fs";
import path from "node:path";
import { generateFrontmatter } from "./frontmatter.mjs";
import { writeNote } from "./note-writer.mjs";
import { inspectXSourceUrl, normalizeXHandle } from "./x-source-registry.mjs";

export function selectXPostsForPromotion(result = {}, options = {}) {
  const posts = Array.isArray(result.x_posts) ? result.x_posts : [];
  const wantedUrls = new Set((options.postUrls || []).map(normalizePostUrl));
  const wantedIds = new Set((options.postIds || []).map(String));
  let selected = posts;
  if (wantedUrls.size > 0) {
    selected = selected.filter((post) => wantedUrls.has(normalizePostUrl(post.post_url)));
  }
  if (wantedIds.size > 0) {
    selected = selected.filter((post) => wantedIds.has(extractPostId(post.post_url)));
  }
  const limit = Number.parseInt(String(options.limit ?? ""), 10);
  return Number.isFinite(limit) && limit > 0 ? selected.slice(0, limit) : selected;
}

export function buildPromotedXRawNote(config, result = {}, post = {}, options = {}) {
  const registry = options.registry || {};
  const handle = normalizeXHandle(post.author_handle || extractHandleFallback(post.post_url));
  const postId = extractPostId(post.post_url);
  const policy = registry.default_policy || {};
  const bucket = normalizeVaultPath(policy.promoted_bucket || `${config.machineRoot}/10-raw/web/x-promoted`);
  const topic = result.request?.topic || `${handle} X post`;
  const capturedAt = normalizeCapturedAt(result.request?.analysis_time || post.posted_at);
  const source = inspectXSourceUrl(post.post_url, registry);
  const title = `${handle} ${postId}`.trim();
  const notePath = path.posix.join(bucket, `${handle || "x-post"}-${postId || "unknown"}.md`);
  const frontmatter = generateFrontmatter("raw", {
    source_type: "web_article",
    topic,
    source_url: post.post_url || "",
    captured_at: capturedAt,
    status: "queued"
  });

  const mediaArtifacts = formatMediaArtifacts(post);
  const request = result.request || {};
  const content = [
    frontmatter,
    "",
    `# ${title}`,
    "",
    "## Request Context",
    "",
    `- Topic: ${topic}`,
    `- Analysis time: ${request.analysis_time || ""}`,
    `- Keywords: ${(request.keywords || []).join(", ")}`,
    `- Allowlist status: ${source.isAllowlisted ? "allowlisted" : "not allowlisted"}`,
    "",
    "## Main Post",
    "",
    `- URL: ${post.post_url || ""}`,
    `- Author: ${post.author_display_name || handle} (@${handle})`,
    `- Posted at: ${post.posted_at || ""}`,
    `- Discovery reason: ${post.discovery_reason || ""}`,
    "",
    post.post_text_raw || post.combined_summary || post.post_summary || "",
    "",
    post.post_summary ? `Summary: ${post.post_summary}` : "",
    "",
    "## Media Artifacts",
    "",
    mediaArtifacts || "- No media artifacts recorded.",
    ""
  ].filter((line, index, lines) => line !== "" || lines[index - 1] !== "").join("\n");

  return {
    path: notePath,
    title,
    content
  };
}

export function importXIndexPosts(config, result = {}, options = {}) {
  const selected = selectXPostsForPromotion(result, options);
  return selected.map((post) => {
    const note = buildPromotedXRawNote(config, result, post, options);
    const existed = fs.existsSync(path.join(config.vaultPath, note.path));
    const writeResult = writeNote(config, note, {
      allowFilesystemFallback: options.allowFilesystemFallback ?? true,
      preferCli: options.preferCli ?? true
    });
    return {
      action: existed ? "update" : "create",
      path: writeResult.path,
      mode: writeResult.mode,
      post_url: post.post_url
    };
  });
}

function formatMediaArtifacts(post) {
  const rows = [];
  for (const artifact of post.artifact_manifest || []) {
    rows.push(`- ${artifact.role || "artifact"}: source=${artifact.source_url || ""} | path=${artifact.path || ""}`);
  }
  for (const media of post.media_items || []) {
    rows.push(`- ${media.media_type || "media"}: source=${media.source_url || ""} | path=${media.local_artifact_path || ""} | ocr=${media.ocr_status || ""}`);
  }
  return rows.join("\n");
}

function normalizePostUrl(url) {
  return String(url || "").trim().replace(/\/+$/g, "");
}

function extractPostId(url) {
  const normalized = normalizePostUrl(url);
  const match = normalized.match(/\/status\/([^/?#]+)/);
  return match ? match[1] : "";
}

function extractHandleFallback(url) {
  try {
    const parsed = new URL(String(url || ""));
    return parsed.pathname.split("/").filter(Boolean)[0] || "";
  } catch {
    return "";
  }
}

function normalizeCapturedAt(value) {
  const text = String(value || "").trim();
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/.test(text)) {
    return text;
  }
  if (text.endsWith("Z")) {
    return text.replace("Z", "+00:00");
  }
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$/.test(text)) {
    return text;
  }
  return new Date().toISOString().slice(0, 19) + "+00:00";
}

function normalizeVaultPath(value) {
  return String(value || "").trim().replace(/\\/g, "/");
}
