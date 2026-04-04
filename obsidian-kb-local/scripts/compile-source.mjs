import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { loadCodexLlmProvider, summarizeLlmProvider } from "../src/codex-config.mjs";
import { executeCompileForRawNote } from "../src/compile-runner.mjs";
import {
  buildCompilePrompt,
  findRawNotes,
  findWikiNotes
} from "../src/compile-pipeline.mjs";

const args = process.argv.slice(2);

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

async function main() {
  const topic = getArg("topic");
  const file = getArg("file");
  const dryRun = hasFlag("dry-run");
  const execute = hasFlag("execute");
  const requestedBatchSize = Number.parseInt(getArg("batch-size") || "10", 10);
  const batchSize = Number.isFinite(requestedBatchSize)
    ? Math.min(Math.max(requestedBatchSize, 1), 10)
    : 10;

  if (!topic && !file) {
    console.error(
      "Usage: node scripts/compile-source.mjs --topic <topic> [--dry-run|--execute] [--batch-size N]"
    );
    console.error(
      "   or: node scripts/compile-source.mjs --file <raw-note-path> [--dry-run|--execute]"
    );
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
}

await main();
