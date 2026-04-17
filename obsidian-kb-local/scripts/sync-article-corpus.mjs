import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { loadCodexLlmProvider, summarizeLlmProvider } from "../src/codex-config.mjs";
import { executeCompileForRawNote } from "../src/compile-runner.mjs";
import {
  deduplicateArticleArtifacts,
  discoverArticleArtifacts,
  getDefaultArticleArtifactRoot,
  importArticleCorpus,
  isLikelyFixtureArticleArtifactPath,
  loadArticleArtifacts
} from "../src/article-corpus.mjs";
import { findRawNotes, findWikiNotes } from "../src/compile-pipeline.mjs";
import { rebuildAutomaticLinks } from "../src/link-graph.mjs";

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

function printUsage() {
  console.error(
    "Usage: node scripts/sync-article-corpus.mjs [--target <file-or-dir>] [--root <artifact-root>] [--workspace-root <path>] [--limit N] [--dry-run] [--compile] [--skip-links]"
  );
}

async function main() {
  const config = loadConfig();
  const workspaceRoot = path.resolve(
    getArg("workspace-root") || path.resolve(config.projectRoot, "..")
  );
  const target = getArg("target");
  const root = path.resolve(getArg("root") || getDefaultArticleArtifactRoot(config.projectRoot));
  const limit = Number.parseInt(getArg("limit") || "0", 10);
  const dryRun = hasFlag("dry-run");
  const compile = hasFlag("compile");
  const skipLinks = hasFlag("skip-links");
  const includeFixtures = hasFlag("include-fixtures");

  let artifacts = [];
  if (target) {
    artifacts = loadArticleArtifacts(target, { workspaceRoot });
  } else {
    artifacts = discoverArticleArtifacts(root).flatMap((artifactPath) =>
      loadArticleArtifacts(artifactPath, { workspaceRoot })
    );
  }

  const filteredArtifacts =
    target || includeFixtures
      ? artifacts
      : artifacts.filter(
          (artifact) => !isLikelyFixtureArticleArtifactPath(artifact.artifactPath)
        );
  const deduped = deduplicateArticleArtifacts(filteredArtifacts);
  const selected =
    Number.isFinite(limit) && limit > 0 ? deduped.slice(0, limit) : deduped;

  if (selected.length === 0) {
    console.log("No article workflow artifacts found.");
    return;
  }

  if (dryRun) {
    for (const artifact of selected) {
      console.log(`${artifact.title} <- ${artifact.artifactPath}`);
    }
    console.log(`\nDry run only. ${selected.length} article artifact(s) matched.`);
    return;
  }

  const importResults = importArticleCorpus(config, selected, {
    allowFilesystemFallback: true,
    preferCli: true
  });

  console.log("Imported article corpus:");
  for (const result of importResults) {
    console.log(
      `${result.action}: ${result.path} (mode: ${result.mode}) <- ${result.artifactPath}`
    );
  }

  const failures = [];

  if (compile) {
    const provider = loadCodexLlmProvider();
    const templateContent = fs.readFileSync(
      path.join(config.projectRoot, "prompts", "compile-source.md"),
      "utf8"
    );

    console.log("");
    console.log(`LLM provider: ${summarizeLlmProvider(provider)}`);
    console.log(`Provider config: ${provider.configPath}`);

    for (const result of importResults) {
      const [rawNote] = findRawNotes(config.vaultPath, config.machineRoot, {
        specificFile: result.path,
        onlyQueued: true
      });

      console.log("");
      console.log(`=== RAW NOTE: ${result.path} ===`);

      if (!rawNote) {
        console.log("Skip compile: raw note is not queued.");
        continue;
      }

      const existingWikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {
        topic: rawNote.frontmatter.topic
      });
      const compileResult = await executeCompileForRawNote(
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

      if (!compileResult.ok) {
        failures.push({
          rawPath: rawNote.relativePath,
          error: compileResult.error.message,
          logFile: compileResult.logFile
        });
        console.error(`Compile failed: ${compileResult.error.message}`);
        console.error(`Raw note marked as error (mode: ${compileResult.rawWriteMode})`);
        console.error(`Error log: ${compileResult.logFile}`);
        continue;
      }

      console.log(`Applied ${compileResult.applyResult.results.length} compile note(s).`);
      console.log(
        `Raw note status: ${compileResult.applyResult.rawStatus} (mode: ${compileResult.applyResult.rawWriteMode})`
      );
      console.log(`Compile log: ${compileResult.applyResult.logFile}`);
      console.log(`Provider endpoint: ${compileResult.response.endpoint}`);

      for (const entry of compileResult.applyResult.results) {
        if (entry.path) {
          console.log(`- ${entry.action}: ${entry.path} (${entry.mode})`);
        } else {
          console.log(`- ${entry.action}: ${entry.title}`);
        }
      }
    }
  }

  if (!skipLinks) {
    const linkResult = rebuildAutomaticLinks(config, {
      allowFilesystemFallback: true,
      preferCli: true
    });
    console.log("");
    console.log(
      `Rebuilt automatic links for ${linkResult.updated} note(s) out of ${linkResult.scanned} scanned.`
    );
  }

  if (failures.length > 0) {
    console.error("");
    console.error(`Sync finished with ${failures.length} compile failure(s).`);
    process.exit(1);
  }
}

if (hasFlag("help") || hasFlag("h")) {
  printUsage();
  process.exit(0);
}

try {
  await main();
} catch (error) {
  printUsage();
  console.error("");
  console.error(error.message);
  process.exit(1);
}
