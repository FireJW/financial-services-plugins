import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { isCliEntrypoint } from "../src/cli-entrypoint.mjs";
import { findWikiNotes } from "../src/compile-pipeline.mjs";
import { parseFrontmatter } from "../src/frontmatter.mjs";
import {
  buildQuerySynthesisNote,
  buildWikiQueryPrompt,
  selectRelevantWikiNotes,
  writeQuerySynthesisNote
} from "../src/wiki-query.mjs";
import { discoverGraphifyTopicWorkspaces } from "../src/graphify-topic-workspaces.mjs";

export function parseQueryWikiCliArgs(args = []) {
  const parsed = {
    query: "",
    topic: "",
    execute: false,
    dryRun: true,
    writeSynthesis: false,
    limit: 8,
    timeoutMs: 240000,
    skipLinks: false,
    skipViews: false
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--query") {
      parsed.query = String(args[++index] || "");
    } else if (arg === "--topic") {
      parsed.topic = String(args[++index] || "");
    } else if (arg === "--execute") {
      parsed.execute = true;
      parsed.dryRun = false;
    } else if (arg === "--dry-run") {
      parsed.dryRun = true;
      parsed.execute = false;
    } else if (arg === "--write-synthesis") {
      parsed.writeSynthesis = true;
    } else if (arg === "--limit") {
      parsed.limit = normalizePositiveInteger(args[++index], parsed.limit);
    } else if (arg === "--timeout-ms") {
      parsed.timeoutMs = normalizePositiveInteger(args[++index], parsed.timeoutMs);
    } else if (arg === "--skip-links") {
      parsed.skipLinks = true;
    } else if (arg === "--skip-views") {
      parsed.skipViews = true;
    }
  }

  if (!parsed.query) {
    const error = new Error("Missing required --query argument.");
    error.code = "USAGE";
    throw error;
  }

  return parsed;
}

export async function executeQueryWikiCommand(command, runtime = {}) {
  const writer = runtime.writer || console;
  const config = runtime.config;
  if (!config) {
    throw new Error("executeQueryWikiCommand requires config");
  }

  const notes = resolveTopicNotes(config, command, writer);
  const selectedNotes = selectRelevantWikiNotes(notes, command.query, { limit: command.limit || 8 });
  const prompt = buildWikiQueryPrompt(runtime.templateContent || "{{NOTE_CONTEXT}}", {
    query: command.query,
    topic: command.topic,
    selectedNotes
  });

  if (command.dryRun || !command.execute) {
    return {
      executed: false,
      selectedNotes,
      prompt
    };
  }

  const answer = runtime.answer || "";
  const synthesis = command.writeSynthesis
    ? (runtime.writeQuerySynthesisNote || writeQuerySynthesisNote)(config, {
        query: command.query,
        topic: command.topic,
        answer,
        selectedNotes
      })
    : buildQuerySynthesisNote(config, {
        query: command.query,
        topic: command.topic,
        answer,
        selectedNotes
      });

  return {
    executed: true,
    selectedNotes,
    prompt,
    writeResult: synthesis.writeResult || synthesis
  };
}

export async function runQueryWikiCli(args = process.argv.slice(2), runtime = {}) {
  const writer = runtime.writer || console;

  if (args.includes("--help") || args.includes("-h")) {
    printUsage(writer);
    return 0;
  }

  try {
    const command = parseQueryWikiCliArgs(args);
    const config = runtime.config || loadConfig();
    const result = await executeQueryWikiCommand(command, {
      ...runtime,
      config,
      writer
    });

    if (result.executed) {
      writer.log(`Selected notes: ${result.selectedNotes.length}`);
      if (result.writeResult?.path) {
        writer.log(`Query synthesis: ${result.writeResult.path}`);
      }
    } else {
      writer.log(result.prompt);
    }

    return 0;
  } catch (error) {
    reportCliError(error, writer.error?.bind(writer) || writer.log?.bind(writer) || console.error);
    return 1;
  }
}

export function reportCliError(error, writer = console.error) {
  if (error?.code === "USAGE") {
    writer("Usage: node scripts/query-wiki.mjs --query <text> [--topic <topic>] [--execute]");
    writer("");
  }
  writer(error?.message || String(error));
}

function printUsage(writer = console.error) {
  const write =
    typeof writer === "function"
      ? writer
      : writer?.error?.bind(writer) || writer?.log?.bind(writer) || console.error;
  write("Usage: node scripts/query-wiki.mjs --query <text> [--topic <topic>] [--execute]");
}

function resolveTopicNotes(config, command, writer) {
  if (!command.topic) {
    return findWikiNotes(config.vaultPath, config.machineRoot, {});
  }

  const exact = findWikiNotes(config.vaultPath, config.machineRoot, { topic: command.topic });
  if (exact.length > 0) {
    writer.log?.(`Topic scope resolution: exact:${command.topic}`);
    return exact;
  }

  const workspace = discoverGraphifyTopicWorkspaces(config.projectRoot).find((entry) => {
    const expected = normalizeLabel(command.topic);
    return normalizeLabel(entry.topic) === expected || normalizeLabel(entry.slug) === expected;
  });
  if (!workspace) {
    writer.log?.(`Topic scope resolution: empty:${command.topic}`);
    return [];
  }

  writer.log?.(`No exact topic notes; falling back to graphify workspace ${workspace.slug}`);
  writer.log?.(`Topic scope resolution: graphify-sidecar:${workspace.slug}`);
  return loadGraphifyWorkspaceWikiNotes(config, workspace);
}

function loadGraphifyWorkspaceWikiNotes(config, workspace) {
  const manifest = readJson(workspace.manifestPath, {});
  const notes = [];
  for (const entry of Array.isArray(manifest.wikiNotes) ? manifest.wikiNotes : []) {
    const filePath = entry.destination || path.join(workspace.root, "input", "wiki", entry.wikiKind || "wiki", path.basename(entry.relativePath || ""));
    if (!fs.existsSync(filePath)) {
      continue;
    }
    const content = fs.readFileSync(filePath, "utf8");
    notes.push({
      fullPath: filePath,
      relativePath: String(entry.relativePath || path.relative(config.vaultPath, filePath)).replace(/\\/g, "/"),
      title: path.basename(filePath, ".md"),
      content,
      frontmatter: parseFrontmatter(content) || {}
    });
  }
  return notes;
}

function normalizeLabel(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-|-$/g, "");
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

if (isCliEntrypoint(import.meta.url)) {
  const exitCode = await runQueryWikiCli();
  process.exit(exitCode);
}
