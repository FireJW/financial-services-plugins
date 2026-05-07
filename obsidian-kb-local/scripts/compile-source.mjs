import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import {
  formatCodexProviderRouteDetail,
  loadCodexLlmProvider,
  summarizeLlmProvider
} from "../src/codex-config.mjs";
import { executeCompileForRawNote } from "../src/compile-runner.mjs";
import {
  buildCompilePrompt,
  findRawNotes,
  findWikiNotes
} from "../src/compile-pipeline.mjs";
import { rebuildAutomaticLinks } from "../src/link-graph.mjs";
import { callResponsesApi } from "../src/llm-provider.mjs";
import { isCliEntrypoint } from "../src/cli-entrypoint.mjs";

const defaultArgs = process.argv.slice(2);

export function parseCompileSourceArgs(inputArgs = []) {
  const parsed = {
    topic: getArgFrom(inputArgs, "topic"),
    file: getArgFrom(inputArgs, "file"),
    dryRun: inputArgs.includes("--dry-run"),
    execute: inputArgs.includes("--execute"),
    skipLinks: inputArgs.includes("--skip-links"),
    probeProviderOnly: inputArgs.includes("--probe-provider-only"),
    compileTimeoutMs: normalizePositiveInteger(getArgFrom(inputArgs, "timeout-ms"), 240000)
  };
  if (parsed.topic === undefined) {
    parsed.topic = null;
  }
  if (parsed.file === undefined) {
    parsed.file = null;
  }
  return parsed;
}

export async function runCompileSourceProviderProbe(config, runtime = {}) {
  const writer = runtime.writer || console;
  const provider = (runtime.loadProvider || (() => loadCodexLlmProvider({ requireApiKey: false })))();
  writer.log(`Provider route: ${formatCodexProviderRouteDetail(provider)}`);
  const callProvider =
    runtime.callProvider ||
    ((activeProvider, prompt, options = {}) =>
      callResponsesApi(activeProvider, prompt, {
        timeoutMs: (options.timeoutMs ?? runtime.timeoutMs) || 240000
      }));
  const probePrompt = "Respond with OK.";
  const probeOptions = {
    timeoutMs: runtime.timeoutMs || 240000,
    config
  };
  const response = await callProvider(provider, probePrompt, probeOptions);
  writer.log(`Provider probe: OK via ${response.endpoint} -> ${response.outputText}`);
  return { provider, response };
}

export async function runCompileSourceCli(inputArgs = defaultArgs, runtime = {}) {
  return main(inputArgs, runtime);
}

function getArg(inputArgs, name) {
  const index = inputArgs.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= inputArgs.length) {
    return null;
  }

  return inputArgs[index + 1];
}

function hasFlag(inputArgs, name) {
  return inputArgs.includes(`--${name}`);
}

function printUsage(writer = console.error) {
  const write =
    typeof writer === "function"
      ? writer
      : writer?.error?.bind(writer) || writer?.log?.bind(writer) || console.error;
  write(
    "Usage: node scripts/compile-source.mjs --topic <topic> [--dry-run|--execute] [--batch-size N] [--skip-links]"
  );
  write(
    "   or: node scripts/compile-source.mjs --file <raw-note-path> [--dry-run|--execute] [--skip-links]"
  );
}

async function main(inputArgs = defaultArgs, runtime = {}) {
  const parsed = parseCompileSourceArgs(inputArgs);
  const writer = runtime.writer || console;

  if (hasFlag(inputArgs, "help") || hasFlag(inputArgs, "h")) {
    printUsage(writer);
    return 0;
  }

  if (parsed.probeProviderOnly) {
    await runCompileSourceProviderProbe(loadConfig(), {
      timeoutMs: parsed.compileTimeoutMs,
      writer
    });
    return 0;
  }

  const topic = getArg(inputArgs, "topic");
  const file = getArg(inputArgs, "file");
  const dryRun = hasFlag(inputArgs, "dry-run");
  const execute = hasFlag(inputArgs, "execute");
  const skipLinks = hasFlag(inputArgs, "skip-links");
  const requestedBatchSize = Number.parseInt(getArg(inputArgs, "batch-size") || "10", 10);
  const batchSize = Number.isFinite(requestedBatchSize)
    ? Math.min(Math.max(requestedBatchSize, 1), 10)
    : 10;

  if (!topic && !file) {
    printUsage(writer);
    return 1;
  }

  if (dryRun && execute) {
    writer.error?.("Choose either --dry-run or --execute, not both.");
    return 1;
  }

  const config = loadConfig();
  const rawNotes = findRawNotes(config.vaultPath, config.machineRoot, {
    topic,
    specificFile: file,
    onlyQueued: true
  }).slice(0, batchSize);

  if (rawNotes.length === 0) {
    writer.log("No queued raw notes found for the requested topic or file.");
    return 0;
  }

  const templateContent = fs.readFileSync(
    path.join(config.projectRoot, "prompts", "compile-source.md"),
    "utf8"
  );
  const provider = execute ? loadCodexLlmProvider() : null;

  if (provider) {
    writer.log(`LLM provider: ${summarizeLlmProvider(provider)}`);
    writer.log(`Provider config: ${provider.configPath}`);
    writer.log("");
  }

  const failures = [];
  let successfulCompiles = 0;

  for (const rawNote of rawNotes) {
    const existingWikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {
      topic: rawNote.frontmatter.topic
    });
    const prompt = buildCompilePrompt(templateContent, rawNote, existingWikiNotes);

    writer.log(`=== RAW NOTE: ${rawNote.relativePath} ===`);
    if (dryRun) {
      writer.log(prompt.slice(0, 1200));
      if (prompt.length > 1200) {
        writer.log("\n...[truncated for dry run preview]...");
      }
    } else if (execute) {
      const result = await executeCompileForRawNote(
        config,
        {
          rawNote,
          existingWikiNotes,
          templateContent,
          provider
        },
        {
          allowFilesystemFallback: true,
          preferCli: true
        }
      );

      if (!result.ok) {
        failures.push({
          rawPath: rawNote.relativePath,
          error: result.error.message,
          logFile: result.logFile
        });
        writer.error?.(`Compile failed: ${result.error.message}`);
        writer.error?.(`Raw note marked as error (mode: ${result.rawWriteMode})`);
        writer.error?.(`Error log: ${result.logFile}`);
      } else {
        successfulCompiles += 1;
        writer.log(`Applied ${result.applyResult.results.length} compile note(s).`);
        writer.log(
          `Raw note status: ${result.applyResult.rawStatus} (mode: ${result.applyResult.rawWriteMode})`
        );
        writer.log(`Compile log: ${result.applyResult.logFile}`);
        writer.log(`Provider endpoint: ${result.response.endpoint}`);

        for (const entry of result.applyResult.results) {
          if (entry.path) {
            writer.log(`- ${entry.action}: ${entry.path} (${entry.mode})`);
          } else {
            writer.log(`- ${entry.action}: ${entry.title}`);
          }
        }
      }
    } else {
      writer.log(prompt);
      writer.log("\nNext step:");
      writer.log(
        `Pipe valid JSON into node scripts/apply-compile-output.mjs --raw-path "${rawNote.relativePath}"`
      );
    }

    writer.log("");
  }

  if (failures.length > 0) {
    writer.error?.(`Compile execution finished with ${failures.length} failure(s).`);
    return 1;
  }

  if (execute && !skipLinks && successfulCompiles > 0) {
    const linkResult = rebuildAutomaticLinks(config, {
      allowFilesystemFallback: true,
      preferCli: true
    });
    writer.log(
      `Automatic links rebuilt for ${linkResult.updated} note(s) out of ${linkResult.scanned} scanned.`
    );
  }

  return 0;
}

if (isCliEntrypoint(import.meta.url)) {
  const exitCode = await runCompileSourceCli();
  process.exit(exitCode);
}

function getArgFrom(inputArgs, name) {
  const index = inputArgs.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= inputArgs.length) {
    return undefined;
  }
  return inputArgs[index + 1];
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
