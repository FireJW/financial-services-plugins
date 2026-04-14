import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { normalizeCodexThreadUri } from "../src/codex-thread-capture.mjs";
import {
  appendCodexThreadCaptureAuditLog,
  normalizeAuditRunId
} from "../src/codex-thread-capture-log.mjs";
import { loadConfig } from "../src/config.mjs";
import { loadCodexThreadBatchManifest } from "./capture-codex-thread-batch.mjs";
import { parseThreadsFromText } from "./init-codex-thread-batch.mjs";

export function parseVerifyCodexThreadCaptureArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const manifestPath = String(getArg(list, "manifest") || "").trim();
  const threadsFile = String(getArg(list, "threads-file") || "").trim();
  const threadUris = getAllArgs(list, "thread-uri");
  const threadIds = getAllArgs(list, "thread-id");
  const runId = String(getArg(list, "run-id") || "").trim();
  const json = hasFlag(list, "json");

  if (!manifestPath && !threadsFile && threadUris.length === 0 && threadIds.length === 0) {
    throw new Error(
      "Provide at least one target via --thread-uri, --thread-id, --threads-file, or --manifest."
    );
  }

  return {
    manifestPath: manifestPath ? path.resolve(manifestPath) : "",
    threadsFile: threadsFile ? path.resolve(threadsFile) : "",
    threadUris,
    threadIds,
    runId,
    json
  };
}

export function collectVerifyThreadUris(command) {
  const refs = [];

  if (command.manifestPath) {
    const manifest = loadCodexThreadBatchManifest(command.manifestPath);
    for (const entry of manifest.entries) {
      refs.push(normalizeCodexThreadUri(entry.threadUri, entry.threadId));
    }
  }

  if (command.threadsFile) {
    if (!fs.existsSync(command.threadsFile)) {
      throw new Error(`threads file does not exist: ${command.threadsFile}`);
    }
    for (const entry of parseThreadsFromText(fs.readFileSync(command.threadsFile, "utf8"))) {
      refs.push(normalizeThreadInput(entry));
    }
  }

  for (const entry of command.threadUris || []) {
    refs.push(normalizeThreadInput(entry));
  }
  for (const entry of command.threadIds || []) {
    refs.push(normalizeThreadInput(entry));
  }

  return [...new Set(refs)];
}

export function verifyCodexThreadCapture(config, threadUris) {
  const notes = scanVaultNotes(config.vaultPath, config.machineRoot);

  return threadUris.map((threadUri) => {
    const rawMatches = [];

    for (const note of notes) {
      const content = note.content;
      const frontmatter = note.frontmatter || {};
      const sourceUrl = String(frontmatter.source_url || "");
      const dedupKey = String(frontmatter.dedup_key || "");
      const containsThreadUri =
        sourceUrl === threadUri ||
        content.includes(`thread_uri: ${threadUri}`) ||
        dedupKey.includes(threadUri);

      if (frontmatter.kb_type === "raw" && containsThreadUri) {
        rawMatches.push({
          path: note.relativePath,
          title: note.title,
          status: String(frontmatter.status || ""),
          sourceUrl
        });
      }
    }

    const rawPaths = new Set(rawMatches.map((entry) => entry.path));
    const wikiMatches = [];
    for (const note of notes) {
      const frontmatter = note.frontmatter || {};
      if (frontmatter.kb_type !== "wiki") {
        continue;
      }
      const compiledFrom = Array.isArray(frontmatter.compiled_from) ? frontmatter.compiled_from : [];
      const dedupKey = String(frontmatter.dedup_key || "");
      const containsThreadUri = dedupKey.includes(threadUri);
      const compiledFromRaw = compiledFrom.filter((entry) => rawPaths.has(entry));
      if (containsThreadUri || compiledFromRaw.length > 0) {
        wikiMatches.push({
          path: note.relativePath,
          title: note.title,
          wikiKind: String(frontmatter.wiki_kind || ""),
          compiledFrom: compiledFromRaw.length > 0 ? compiledFromRaw : compiledFrom
        });
      }
    }

    return {
      threadUri,
      ok: rawMatches.length > 0,
      rawCount: rawMatches.length,
      wikiCount: wikiMatches.length,
      rawMatches,
      wikiMatches
    };
  });
}

export async function runVerifyCodexThreadCapture(args = process.argv.slice(2), runtime = {}) {
  const command = parseVerifyCodexThreadCaptureArgs(args);
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const runId = normalizeAuditRunId(command.runId);
  const threadUris = collectVerifyThreadUris(command);
  const results = verifyCodexThreadCapture(config, threadUris);
  const captured = results.filter((entry) => entry.ok).length;
  const missing = results.length - captured;

  appendCodexThreadCaptureAuditLog(config.projectRoot, "verify-codex-thread-capture", {
    action: "verify-codex-thread-capture",
    run_id: runId,
    total: results.length,
    captured,
    missing,
    raw_match_count: results.reduce((sum, entry) => sum + entry.rawCount, 0),
    wiki_match_count: results.reduce((sum, entry) => sum + entry.wikiCount, 0),
    thread_uris: threadUris,
    captured_thread_uris: results.filter((entry) => entry.ok).map((entry) => entry.threadUri),
    missing_thread_uris: results.filter((entry) => !entry.ok).map((entry) => entry.threadUri)
  });

  if (command.json) {
    writer.log(JSON.stringify(results, null, 2));
    return results;
  }

  for (const result of results) {
    writer.log(`=== THREAD: ${result.threadUri} ===`);
    writer.log(`Status: ${result.ok ? "captured" : "missing"}`);
    writer.log(`Raw matches: ${result.rawCount}`);
    for (const entry of result.rawMatches) {
      writer.log(`- raw: ${entry.path} (status=${entry.status || "unknown"})`);
    }
    writer.log(`Wiki matches: ${result.wikiCount}`);
    for (const entry of result.wikiMatches) {
      writer.log(`- wiki:${entry.wikiKind || "unknown"} ${entry.path}`);
    }
    writer.log("");
  }

  writer.log(`Verify summary: total=${results.length}, captured=${captured}, missing=${missing}`);
  return results;
}

function printUsage(writer = console.error) {
  writer(
    "Usage: node scripts/verify-codex-thread-capture.mjs [--thread-uri <codex://threads/...>] [--thread-id <id>] [--threads-file <path>] [--manifest <path>] [--json]"
  );
}

async function main(args = process.argv.slice(2)) {
  if (hasFlag(args, "help") || hasFlag(args, "h")) {
    printUsage(console.error);
    process.exit(0);
  }

  try {
    const results = await runVerifyCodexThreadCapture(args);
    if (results.some((entry) => !entry.ok)) {
      process.exit(1);
    }
  } catch (error) {
    printUsage(console.error);
    console.error("");
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

function scanVaultNotes(vaultPath, machineRoot) {
  const root = path.join(vaultPath, machineRoot);
  const files = walkMarkdownFiles(root);
  return files.map((fullPath) => {
    const content = fs.readFileSync(fullPath, "utf8");
    const frontmatter = parseFrontmatter(content);
    return {
      fullPath,
      relativePath: path.relative(vaultPath, fullPath).replace(/\\/g, "/"),
      title: path.basename(fullPath, ".md"),
      content,
      frontmatter
    };
  });
}

function walkMarkdownFiles(directory) {
  const results = [];
  if (!fs.existsSync(directory)) {
    return results;
  }

  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkMarkdownFiles(fullPath));
      continue;
    }
    if (entry.isFile() && entry.name.endsWith(".md")) {
      results.push(fullPath);
    }
  }

  return results;
}

function parseFrontmatter(content) {
  const match = String(content || "").match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) {
    return {};
  }

  const result = {};
  for (const line of match[1].split(/\r?\n/)) {
    const colonIndex = line.indexOf(":");
    if (colonIndex === -1) {
      continue;
    }
    const key = line.slice(0, colonIndex).trim();
    let value = line.slice(colonIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value.startsWith("[") && value.endsWith("]")) {
      value = value
        .slice(1, -1)
        .split(",")
        .map((entry) => entry.trim().replace(/^"(.*)"$/, "$1"))
        .filter(Boolean);
    }
    result[key] = value;
  }
  return result;
}

function normalizeThreadInput(value) {
  const text = String(value || "").trim();
  if (!text) {
    throw new Error("Thread input cannot be empty.");
  }
  return text.startsWith("codex://threads/")
    ? normalizeCodexThreadUri(text)
    : normalizeCodexThreadUri("", text);
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
  return values;
}

function hasFlag(args, name) {
  return args.includes(`--${name}`);
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
  await main();
}
