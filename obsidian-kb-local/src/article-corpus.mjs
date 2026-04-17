import fs from "node:fs";
import path from "node:path";
import { formatIso8601Tz } from "./frontmatter.mjs";
import { ingestRawNote, sanitizeFilename } from "./ingest.mjs";

const ARTICLE_RESULT_FILENAME = "article-publish-result.json";
const PUBLISH_PACKAGE_FILENAME = "publish-package.json";
const FIXTURE_ARTIFACT_MARKERS = [
  "canonical",
  "debug",
  "probe",
  "test",
  "/tests/",
  "/fixtures/",
  "/fixture/",
  "smoke",
  "/_reuse-smoke/",
  "/article-cli-smoke/",
  "placeholder",
  "diagnostic",
  "/workflow-rerun-",
  "/x-index-screenshot-publish-replay/"
];

export function getDefaultArticleArtifactRoot(projectRoot) {
  return path.resolve(projectRoot, "..", ".tmp");
}

export function discoverArticleArtifacts(rootPath) {
  const grouped = new Map();
  walkArtifactTree(path.resolve(rootPath), grouped);

  return [...grouped.values()]
    .map((entry) => entry.resultPath || entry.publishPackagePath)
    .filter(Boolean)
    .sort();
}

export function isLikelyFixtureArticleArtifactPath(artifactPath) {
  const normalized = String(artifactPath ?? "").replace(/\\/g, "/").toLowerCase();
  return FIXTURE_ARTIFACT_MARKERS.some((marker) => normalized.includes(marker));
}

export function loadArticleArtifacts(targetPath, options = {}) {
  const resolved = path.resolve(targetPath);
  const stat = fs.statSync(resolved);

  if (stat.isDirectory()) {
    return discoverArticleArtifacts(resolved).map((entry) =>
      loadSingleArticleArtifact(entry, options)
    );
  }

  return [loadSingleArticleArtifact(resolved, options)];
}

export function deduplicateArticleArtifacts(artifacts) {
  const winners = new Map();

  for (const artifact of artifacts) {
    const dedupKey = normalizeText(artifact.title);
    if (!dedupKey) {
      continue;
    }

    const existing = winners.get(dedupKey);
    if (!existing || artifact.analysisTimestamp > existing.analysisTimestamp) {
      winners.set(dedupKey, artifact);
    }
  }

  return [...winners.values()].sort(
    (left, right) =>
      right.analysisTimestamp - left.analysisTimestamp ||
      left.title.localeCompare(right.title)
  );
}

export function importArticleCorpus(config, artifacts, options = {}) {
  const results = [];

  for (const artifact of artifacts) {
    const notePath = `${config.machineRoot}/10-raw/articles/${sanitizeFilename(artifact.title)}.md`;
    const fullPath = path.join(config.vaultPath, notePath);
    const existed = fs.existsSync(fullPath);

    const writeResult = ingestRawNote(
      config,
      {
        sourceType: "article",
        topic: artifact.topic,
        sourceUrl: artifact.sourceUrl,
        title: artifact.title,
        body: formatArticleCorpusBody(artifact),
        capturedAt: artifact.analysisTime,
        status: options.status || "queued"
      },
      {
        allowFilesystemFallback: options.allowFilesystemFallback ?? true,
        preferCli: options.preferCli ?? true
      }
    );

    results.push({
      action: existed ? "update" : "create",
      title: artifact.title,
      path: writeResult.path,
      mode: writeResult.mode,
      artifactPath: artifact.artifactPath
    });
  }

  return results;
}

export function formatArticleCorpusBody(article) {
  const lines = [
    "> Imported from an existing article workflow output so Codex can reuse it as local article corpus.",
    "",
    "## Corpus Metadata",
    "",
    `- Topic: ${article.topic}`,
    `- Analysis time: ${article.analysisTime}`,
    `- Publication readiness: ${article.publicationReadiness || "unknown"}`,
    `- Review gate: ${article.reviewStatus || "unknown"}`,
    `- Imported from: ${article.artifactPath}`
  ];

  if (article.publishPackagePath) {
    lines.push(`- Publish package: ${article.publishPackagePath}`);
  }

  if (article.workflowResultPath) {
    lines.push(`- Workflow result: ${article.workflowResultPath}`);
  }

  if (article.feedbackPath) {
    lines.push(`- Feedback markdown: ${article.feedbackPath}`);
  }

  if (article.digest) {
    lines.push("", "## Digest", "", article.digest);
  }

  if (article.keywords.length > 0) {
    lines.push("", "## Keywords", "");
    for (const keyword of article.keywords) {
      lines.push(`- ${keyword}`);
    }
  }

  if (article.sourceItems.length > 0) {
    lines.push("", "## Source Map", "");
    for (const item of article.sourceItems) {
      const label = [item.sourceName, item.sourceType].filter(Boolean).join(" | ");
      const summary = item.summary ? ` | ${item.summary}` : "";
      lines.push(`- ${label || "source"} | ${item.url || "no-url"}${summary}`);
    }
  }

  lines.push(
    "",
    "## Article Markdown",
    "",
    stripLeadingTitleHeading(article.contentMarkdown, article.title) ||
      "_No article markdown was available in this artifact._"
  );

  return `${lines.join("\n").trim()}\n`;
}

function loadSingleArticleArtifact(filePath, options = {}) {
  const resolved = path.resolve(filePath);
  const fileName = path.basename(resolved);
  const payload = readJsonFile(resolved);
  const workspaceRoot = options.workspaceRoot
    ? path.resolve(options.workspaceRoot)
    : path.resolve(path.dirname(resolved), "..", "..");

  if (fileName === ARTICLE_RESULT_FILENAME) {
    return normalizeArticlePublishResult(payload, resolved, workspaceRoot);
  }

  if (fileName === PUBLISH_PACKAGE_FILENAME) {
    return normalizePublishPackage(payload, resolved, workspaceRoot);
  }

  throw new Error(`Unsupported article artifact: ${resolved}`);
}

function normalizeArticlePublishResult(payload, artifactPath, workspaceRoot) {
  const publishPackage = safeObject(payload.publish_package);
  const selectedTopic = safeObject(payload.selected_topic);
  const workflowStage = safeObject(payload.workflow_stage);
  const reviewGate = safeObject(payload.review_gate);
  const manualReview = safeObject(payload.manual_review);
  const title =
    cleanText(publishPackage.title) ||
    cleanText(selectedTopic.title) ||
    path.basename(path.dirname(artifactPath));
  const analysisTime =
    cleanText(payload.analysis_time) || formatIso8601Tz(fs.statSync(artifactPath).mtime);
  const workflowResultPath = resolveArtifactReference(
    workflowStage.result_path,
    path.dirname(artifactPath),
    workspaceRoot
  );
  const feedbackPath = workflowResultPath
    ? resolveArtifactReference(
        path.join(path.dirname(workflowStage.result_path || ""), "workflow", "ARTICLE-FEEDBACK.md"),
        path.dirname(artifactPath),
        workspaceRoot
      )
    : "";

  return {
    artifactPath,
    artifactKind: "article_publish_result",
    title,
    topic: cleanText(selectedTopic.title) || title,
    analysisTime,
    analysisTimestamp: Date.parse(analysisTime) || fs.statSync(artifactPath).mtimeMs,
    sourceUrl: buildWorkflowSourceUrl(title),
    digest: cleanText(publishPackage.digest) || cleanText(selectedTopic.summary),
    keywords: uniqueStrings([
      ...safeStringArray(publishPackage.keywords),
      ...safeStringArray(selectedTopic.keywords)
    ]),
    contentMarkdown:
      normalizeMultiline(publishPackage.content_markdown) ||
      normalizeMultiline(firstArticleContent(publishPackage)) ||
      "",
    publicationReadiness:
      cleanText(payload.publication_readiness) ||
      cleanText(publishPackage.publication_readiness) ||
      "unknown",
    reviewStatus:
      cleanText(reviewGate.status) ||
      cleanText(manualReview.status) ||
      "unknown",
    publishPackagePath: resolveArtifactReference(
      payload.publish_package_path,
      path.dirname(artifactPath),
      workspaceRoot
    ),
    workflowResultPath,
    feedbackPath,
    sourceItems: normalizeSourceItems(selectedTopic.source_items)
  };
}

function normalizePublishPackage(payload, artifactPath, workspaceRoot) {
  const title =
    cleanText(payload.title) || path.basename(path.dirname(artifactPath));
  const analysisTime = formatIso8601Tz(fs.statSync(artifactPath).mtime);

  return {
    artifactPath,
    artifactKind: "publish_package",
    title,
    topic: title,
    analysisTime,
    analysisTimestamp: fs.statSync(artifactPath).mtimeMs,
    sourceUrl: buildWorkflowSourceUrl(title),
    digest: cleanText(payload.digest),
    keywords: safeStringArray(payload.keywords),
    contentMarkdown:
      normalizeMultiline(payload.content_markdown) ||
      normalizeMultiline(firstArticleContent(payload)) ||
      "",
    publicationReadiness:
      cleanText(payload.publication_readiness) || "unknown",
    reviewStatus: "unknown",
    publishPackagePath: resolveArtifactReference(artifactPath, path.dirname(artifactPath), workspaceRoot),
    workflowResultPath: "",
    feedbackPath: "",
    sourceItems: []
  };
}

function normalizeSourceItems(items) {
  return safeArray(items)
    .map((item) => ({
      sourceName: cleanText(item.source_name),
      sourceType: cleanText(item.source_type),
      summary: cleanText(item.summary),
      url: cleanText(item.url)
    }))
    .filter((item) => item.sourceName || item.url || item.summary);
}

function buildWorkflowSourceUrl(title) {
  return `workflow://article-corpus/${encodeURIComponent(sanitizeFilename(title).toLowerCase())}`;
}

function resolveArtifactReference(reference, baseDir, workspaceRoot) {
  const text = cleanText(reference);
  if (!text) {
    return "";
  }

  if (path.isAbsolute(text)) {
    return path.normalize(text);
  }

  if (text.startsWith(".tmp") || text.startsWith("./") || text.startsWith(".\\")) {
    return path.resolve(workspaceRoot, text);
  }

  return path.resolve(baseDir, text);
}

function stripLeadingTitleHeading(markdown, title) {
  const normalized = String(markdown ?? "").replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return "";
  }

  const headingPattern = new RegExp(
    `^#\\s+${escapeRegExp(cleanText(title))}\\s*\\n+`,
    "i"
  );
  return normalized.replace(headingPattern, "").trim();
}

function firstArticleContent(publishPackage) {
  const articles = safeArray(publishPackage.articles);
  if (articles.length === 0) {
    return "";
  }

  const first = safeObject(articles[0]);
  return normalizeMultiline(first.content_markdown) || normalizeMultiline(first.content);
}

function walkArtifactTree(directory, grouped) {
  let entries = [];
  try {
    entries = fs.readdirSync(directory, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      walkArtifactTree(fullPath, grouped);
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    if (entry.name !== ARTICLE_RESULT_FILENAME && entry.name !== PUBLISH_PACKAGE_FILENAME) {
      continue;
    }

    const key = path.dirname(fullPath);
    const current = grouped.get(key) ?? {};
    if (entry.name === ARTICLE_RESULT_FILENAME) {
      current.resultPath = fullPath;
    } else {
      current.publishPackagePath = fullPath;
    }
    grouped.set(key, current);
  }
}

function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function safeStringArray(value) {
  return safeArray(value)
    .map((item) => cleanText(item))
    .filter(Boolean);
}

function uniqueStrings(values) {
  return [...new Set(values.filter(Boolean))];
}

function cleanText(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function normalizeText(value) {
  return cleanText(value).toLowerCase();
}

function normalizeMultiline(value) {
  return String(value ?? "").replace(/\r\n/g, "\n").trim();
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function readJsonFile(filePath) {
  const text = fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, "");
  return JSON.parse(text);
}
