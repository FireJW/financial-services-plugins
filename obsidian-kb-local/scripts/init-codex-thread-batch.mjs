import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_SOURCE_LABEL = "Codex batch import";
const DEFAULT_TITLE_PREFIX = "Codex thread";

export function parseInitCodexThreadBatchArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const outputDir = cleanText(getArg(list, "output-dir"));
  if (!outputDir) {
    throw new Error("Missing required --output-dir argument.");
  }

  const codexHome = cleanText(getArg(list, "codex-home"));
  const sessionIndexPath =
    cleanText(getArg(list, "session-index")) || resolveCodexSessionIndexPath(codexHome);

  return {
    outputDir: path.resolve(outputDir),
    threadsFile: resolveOptionalPath(getArg(list, "threads-file")),
    threadUris: getAllArgs(list, "thread-uri"),
    threadIds: getAllArgs(list, "thread-id"),
    topic: cleanText(getArg(list, "topic")),
    titlePrefix: cleanText(getArg(list, "title-prefix")) || DEFAULT_TITLE_PREFIX,
    sourceLabel: cleanText(getArg(list, "source-label")) || DEFAULT_SOURCE_LABEL,
    compile: hasFlag(list, "no-compile") ? false : true,
    sessionIndexPath
  };
}

export function parseThreadsFromText(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
}

export function collectCodexThreadRefs(command = {}) {
  const refs = [];
  if (command.threadsFile) {
    if (!fs.existsSync(command.threadsFile)) {
      throw new Error(`threads file does not exist: ${command.threadsFile}`);
    }
    refs.push(...parseThreadsFromText(fs.readFileSync(command.threadsFile, "utf8")));
  }
  refs.push(...(command.threadUris || []));
  refs.push(...(command.threadIds || []));

  const byUri = new Map();
  for (const rawRef of refs) {
    const normalized = normalizeThreadRef(rawRef);
    if (!normalized.threadUri || byUri.has(normalized.threadUri)) {
      continue;
    }
    byUri.set(normalized.threadUri, normalized);
  }
  return [...byUri.values()];
}

export function loadCodexThreadNameIndex(sessionIndexPath) {
  const index = new Map();
  const resolvedPath = cleanText(sessionIndexPath);
  if (!resolvedPath || !fs.existsSync(resolvedPath)) {
    return index;
  }

  const lines = fs.readFileSync(resolvedPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    try {
      const payload = JSON.parse(trimmed);
      const id = cleanText(payload.id ?? payload.thread_id);
      const threadName = cleanText(payload.thread_name ?? payload.threadName ?? payload.name);
      if (id && threadName) {
        index.set(id, {
          threadName,
          updatedAt: cleanText(payload.updated_at ?? payload.updatedAt)
        });
      }
    } catch {
      // Keep batch initialization tolerant of partially-written JSONL logs.
    }
  }
  return index;
}

export function buildCodexThreadBatchInitPlan(command = {}) {
  const outputDir = path.resolve(cleanText(command.outputDir));
  if (!outputDir) {
    throw new Error("Missing outputDir.");
  }

  const refs = collectCodexThreadRefs(command);
  if (refs.length === 0) {
    throw new Error("Provide at least one thread via --thread-uri, --thread-id, or --threads-file.");
  }

  const threadNameIndex = loadCodexThreadNameIndex(command.sessionIndexPath);
  const bodiesDirectory = path.join(outputDir, "bodies");
  const usedFilenames = new Set();
  const entries = refs.map((ref, index) => {
    const nameEntry = threadNameIndex.get(ref.threadId);
    const threadName = cleanText(nameEntry?.threadName);
    const title = buildThreadTitle(command.titlePrefix, threadName, ref.threadId, index);
    const bodyFilename = uniqueFilename(sanitizeFilename(title || ref.threadId), usedFilenames);
    const bodyPath = path.join(bodiesDirectory, bodyFilename);
    const entry = {
      threadUri: ref.threadUri,
      threadId: ref.threadId,
      threadName,
      topic: cleanText(command.topic),
      title,
      bodyPath,
      bodyFile: path.posix.join("bodies", bodyFilename),
      sourceLabel: cleanText(command.sourceLabel) || DEFAULT_SOURCE_LABEL,
      compile: command.compile !== false
    };
    return {
      ...entry,
      bodyTemplate: buildCodexThreadBodyTemplate(entry)
    };
  });

  return {
    outputDir,
    bodiesDirectory,
    manifestPath: path.join(outputDir, "manifest.json"),
    entries,
    manifest: {
      defaults: {
        source_label: cleanText(command.sourceLabel) || DEFAULT_SOURCE_LABEL,
        compile: command.compile !== false,
        status: "queued",
        topic: cleanText(command.topic)
      },
      entries: entries.map((entry) => {
        const manifestEntry = {
          thread_uri: entry.threadUri,
          thread_id: entry.threadId,
          topic: entry.topic,
          title: entry.title,
          body_file: entry.bodyFile
        };
        if (entry.threadName) {
          manifestEntry.thread_name = entry.threadName;
        }
        return manifestEntry;
      })
    }
  };
}

export function buildCodexThreadBodyTemplate(entry = {}) {
  const metadata = [
    `Thread URI: ${cleanText(entry.threadUri) || "codex://threads/current-thread"}`,
    cleanText(entry.threadName) ? `Thread name: ${cleanText(entry.threadName)}` : "",
    cleanText(entry.title) ? `Title: ${cleanText(entry.title)}` : "",
    cleanText(entry.topic) ? `Topic: ${cleanText(entry.topic)}` : ""
  ].filter(Boolean);

  const lines = [
    "# Codex Thread Capture",
    "",
    ...metadata,
    "",
    "## User Request",
    "",
    "<paste or summarize the user request here>",
    "",
    "## Assistant Response",
    "",
    "<paste or summarize the final useful response here>",
    ""
  ];
  return lines.join("\n");
}

export function writeCodexThreadBatchInitPlan(plan) {
  fs.mkdirSync(plan.bodiesDirectory, { recursive: true });
  fs.writeFileSync(plan.manifestPath, `${JSON.stringify(plan.manifest, null, 2)}\n`, "utf8");
  for (const entry of plan.entries) {
    if (!fs.existsSync(entry.bodyPath)) {
      fs.writeFileSync(entry.bodyPath, entry.bodyTemplate, "utf8");
    }
  }
  return plan;
}

export async function runInitCodexThreadBatch(args = process.argv.slice(2), runtime = {}) {
  const command = parseInitCodexThreadBatchArgs(args);
  const plan = writeCodexThreadBatchInitPlan(buildCodexThreadBatchInitPlan(command));
  const writer = runtime.writer || console;
  writer.log(`Batch manifest: ${plan.manifestPath}`);
  writer.log(`Body templates: ${plan.bodiesDirectory}`);
  writer.log(`Entries: ${plan.entries.length}`);
  return plan;
}

function buildThreadTitle(prefix, threadName, threadId, index) {
  const titlePrefix = cleanText(prefix);
  if (threadName) {
    return titlePrefix ? `${titlePrefix} - ${threadName}` : threadName;
  }
  const fallback = cleanText(threadId) || `thread-${index + 1}`;
  return titlePrefix ? `${titlePrefix} - ${fallback}` : fallback;
}

function normalizeThreadRef(value) {
  const raw = cleanText(value);
  if (!raw) {
    return { threadId: "", threadUri: "" };
  }
  if (raw.startsWith("codex://threads/")) {
    const threadId = raw.slice("codex://threads/".length);
    return { threadId, threadUri: raw };
  }
  return { threadId: raw, threadUri: `codex://threads/${raw}` };
}

function uniqueFilename(base, usedFilenames) {
  const safeBase = base || "codex-thread";
  let candidate = `${safeBase}.md`;
  let index = 2;
  while (usedFilenames.has(candidate.toLowerCase())) {
    candidate = `${safeBase}-${index}.md`;
    index += 1;
  }
  usedFilenames.add(candidate.toLowerCase());
  return candidate;
}

function sanitizeFilename(value) {
  return String(value || "")
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 100);
}

function resolveCodexSessionIndexPath(codexHome) {
  const home = cleanText(codexHome) || cleanText(process.env.CODEX_HOME) || path.join(os.homedir(), ".codex");
  return path.join(home, "session_index.jsonl");
}

function resolveOptionalPath(value) {
  const cleaned = cleanText(value);
  return cleaned ? path.resolve(cleaned) : "";
}

function getArg(args, name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }
  return args[index + 1];
}

function getAllArgs(args, name) {
  const values = [];
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === `--${name}` && index + 1 < args.length) {
      values.push(args[index + 1]);
      index += 1;
    }
  }
  return values.map(cleanText).filter(Boolean);
}

function hasFlag(args, name) {
  return args.includes(`--${name}`);
}

function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function printUsage(writer = console.error) {
  writer(
    "Usage: node scripts/init-codex-thread-batch.mjs --output-dir <path> [--thread-id <id> ... | --thread-uri <codex://threads/...> ... | --threads-file <path>] [--session-index <path>] [--topic <topic>] [--title-prefix <prefix>] [--no-compile]"
  );
}

function isDirectExecution() {
  if (!process.argv[1]) {
    return false;
  }
  try {
    return pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
  } catch {
    return false;
  }
}

if (isDirectExecution()) {
  try {
    await runInitCodexThreadBatch();
  } catch (error) {
    printUsage(console.error);
    console.error("");
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
