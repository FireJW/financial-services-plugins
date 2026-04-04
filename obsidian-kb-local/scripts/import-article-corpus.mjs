import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import {
  deduplicateArticleArtifacts,
  discoverArticleArtifacts,
  getDefaultArticleArtifactRoot,
  isLikelyFixtureArticleArtifactPath,
  importArticleCorpus,
  loadArticleArtifacts
} from "../src/article-corpus.mjs";
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
    "Usage: node scripts/import-article-corpus.mjs [--target <file-or-dir>] [--root <artifact-root>] [--workspace-root <path>] [--limit N] [--dry-run] [--skip-links]"
  );
}

function main() {
  const config = loadConfig();
  const workspaceRoot = path.resolve(
    getArg("workspace-root") || path.resolve(config.projectRoot, "..")
  );
  const target = getArg("target");
  const root = path.resolve(getArg("root") || getDefaultArticleArtifactRoot(config.projectRoot));
  const limit = Number.parseInt(getArg("limit") || "0", 10);
  const dryRun = hasFlag("dry-run");
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

  for (const result of importResults) {
    console.log(
      `${result.action}: ${result.path} (mode: ${result.mode}) <- ${result.artifactPath}`
    );
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
}

if (hasFlag("help") || hasFlag("h")) {
  printUsage();
  process.exit(0);
}

try {
  main();
} catch (error) {
  printUsage();
  console.error("");
  console.error(error.message);
  process.exit(1);
}
