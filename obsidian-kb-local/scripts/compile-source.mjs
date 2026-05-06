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

const args = process.argv.slice(2);

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
    ((activeProvider) =>
      callResponsesApi(activeProvider, {
        input: "Respond with OK.",
        timeoutMs: runtime.timeoutMs || 240000
      }));
  const response = await callProvider(provider, {
    input: "Respond with OK.",
    timeoutMs: runtime.timeoutMs || 240000,
    config
  });
  writer.log(`Provider probe: OK via ${response.endpoint} -> ${response.outputText}`);
  return { provider, response };
}

function getArg(name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }

  return args[index + 1];
}

function hasFlag(name) {
  return args.includes(`--${name}`);
}

function printUsage() {
  console.error(
    "Usage: node scripts/compile-source.mjs --topic <topic> [--dry-run|--execute] [--batch-size N] [--skip-links]"
  );
  console.error(
    "   or: node scripts/compile-source.mjs --file <raw-note-path> [--dry-run|--execute] [--skip-links]"
  );
}

async function main() {
  const parsed = parseCompileSourceArgs(args);
  if (hasFlag("help") || hasFlag("h")) {
    printUsage();
    process.exit(0);
  }

  if (parsed.probeProviderOnly) {
    await runCompileSourceProviderProbe(loadConfig(), {
      timeoutMs: parsed.compileTimeoutMs
    });
    return;
  }

  const topic = getArg("topic");
  const file = getArg("file");
  const dryRun = hasFlag("dry-run");
  const execute = hasFlag("execute");
  const skipLinks = hasFlag("skip-links");
  const requestedBatchSize = Number.parseInt(getArg("batch-size") || "10", 10);
  const batchSize = Number.isFinite(requestedBatchSize)
    ? Math.min(Math.max(requestedBatchSize, 1), 10)
    : 10;

  if (!topic && !file) {
    printUsage();
    process.exit(1);
  }

  if (dryRun && execute) {
    console.error("Choose either --dry-run or --execute, not both.");
    process.exit(1);
  }

  const config = loadConfig();
  const rawNotes = findRawNotes(config.vaultPath, config.machineRoot, {
    topic,
    specificFile: file,
    onlyQueued: true
  }).slice(0, batchSize);

  if (rawNotes.length === 0) {
    console.log("No queued raw notes found for the requested topic or file.");
    process.exit(0);
  }

  const templateContent = fs.readFileSync(
    path.join(config.projectRoot, "prompts", "compile-source.md"),
    "utf8"
  );
  const provider = execute ? loadCodexLlmProvider() : null;

  if (provider) {
    console.log(`LLM provider: ${summarizeLlmProvider(provider)}`);
    console.log(`Provider config: ${provider.configPath}`);
    console.log("");
  }

  const failures = [];
  let successfulCompiles = 0;

  for (const rawNote of rawNotes) {
    const existingWikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {
      topic: rawNote.frontmatter.topic
    });
    const prompt = buildCompilePrompt(templateContent, rawNote, existingWikiNotes);

    console.log(`=== RAW NOTE: ${rawNote.relativePath} ===`);
    if (dryRun) {
      console.log(prompt.slice(0, 1200));
      if (prompt.length > 1200) {
        console.log("\n...[truncated for dry run preview]...");
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
        console.error(`Compile failed: ${result.error.message}`);
        console.error(`Raw note marked as error (mode: ${result.rawWriteMode})`);
        console.error(`Error log: ${result.logFile}`);
      } else {
        successfulCompiles += 1;
        console.log(`Applied ${result.applyResult.results.length} compile note(s).`);
        console.log(
          `Raw note status: ${result.applyResult.rawStatus} (mode: ${result.applyResult.rawWriteMode})`
        );
        console.log(`Compile log: ${result.applyResult.logFile}`);
        console.log(`Provider endpoint: ${result.response.endpoint}`);

        for (const entry of result.applyResult.results) {
          if (entry.path) {
            console.log(`- ${entry.action}: ${entry.path} (${entry.mode})`);
          } else {
            console.log(`- ${entry.action}: ${entry.title}`);
          }
        }
      }
    } else {
      console.log(prompt);
      console.log("\nNext step:");
      console.log(
        `Pipe valid JSON into node scripts/apply-compile-output.mjs --raw-path "${rawNote.relativePath}"`
      );
    }

    console.log("");
  }

  if (failures.length > 0) {
    console.error(`Compile execution finished with ${failures.length} failure(s).`);
    process.exit(1);
  }

  if (execute && !skipLinks && successfulCompiles > 0) {
    const linkResult = rebuildAutomaticLinks(config, {
      allowFilesystemFallback: true,
      preferCli: true
    });
    console.log(
      `Automatic links rebuilt for ${linkResult.updated} note(s) out of ${linkResult.scanned} scanned.`
    );
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
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
