import { findRawNotes, findWikiNotes } from "../src/compile-pipeline.mjs";

export function parseImportXIndexCliArgs(args = []) {
  const parsed = {
    inputPath: "",
    postIds: [],
    topic: "",
    compile: false,
    healthCheck: true,
    rebuildTopic: false,
    smartCloseout: false,
    skipLinks: false,
    timeoutMs: 240000
  };
  let sawHealthCheck = false;
  let sawSkipHealthCheck = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--input") {
      parsed.inputPath = String(args[++index] || "");
    } else if (arg === "--post-id") {
      parsed.postIds.push(String(args[++index] || ""));
    } else if (arg === "--topic") {
      parsed.topic = String(args[++index] || "");
    } else if (arg === "--compile") {
      parsed.compile = true;
    } else if (arg === "--health-check") {
      sawHealthCheck = true;
      parsed.healthCheck = true;
    } else if (arg === "--skip-health-check") {
      sawSkipHealthCheck = true;
      parsed.healthCheck = false;
    } else if (arg === "--rebuild-topic") {
      parsed.rebuildTopic = true;
    } else if (arg === "--smart-closeout") {
      parsed.smartCloseout = true;
    } else if (arg === "--skip-links") {
      parsed.skipLinks = true;
    } else if (arg === "--timeout-ms") {
      parsed.timeoutMs = normalizePositiveInteger(args[++index], parsed.timeoutMs);
    }
  }

  if (sawHealthCheck && sawSkipHealthCheck) {
    throw new Error("Choose either --health-check or --skip-health-check, not both.");
  }

  return parsed;
}

export function decideTopicRebuild(params = {}) {
  const { config, successfulCompiles = 0, options = {} } = params;
  if (successfulCompiles <= 0) {
    return false;
  }
  if (options.rebuildTopic) {
    return true;
  }
  if (!options.smartCloseout || !options.topic) {
    return false;
  }

  const rawNotes = findRawNotes(config.vaultPath, config.machineRoot, {
    topic: options.topic,
    onlyQueued: false
  });
  const wikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {
    topic: options.topic
  });
  const newestRaw = rawNotes
    .map((note) => String(note.frontmatter?.captured_at || note.frontmatter?.kb_date || ""))
    .sort()
    .at(-1);

  if (!newestRaw || wikiNotes.length === 0) {
    return rawNotes.length > 0;
  }

  return wikiNotes.some((note) => {
    const compiledAt = String(note.frontmatter?.compiled_at || note.frontmatter?.kb_date || "");
    return compiledAt && compiledAt < newestRaw;
  });
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
