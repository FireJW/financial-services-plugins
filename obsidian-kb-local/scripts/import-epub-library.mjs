import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import {
  deduplicateEpubArtifacts,
  discoverEpubFiles,
  getDefaultEpubRoots,
  importEpubLibrary,
  loadEpubArtifacts
} from "../src/epub-library.mjs";
import { rebuildAutomaticLinks } from "../src/link-graph.mjs";

const args = process.argv.slice(2);

function getArg(name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }

  return args[index + 1];
}

function getArgs(name) {
  const values = [];
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === `--${name}` && index + 1 < args.length) {
      values.push(args[index + 1]);
      index += 1;
    }
  }
  return values;
}

function hasFlag(name) {
  return args.includes(`--${name}`);
}

function printUsage() {
  console.error(
    "Usage: node scripts/import-epub-library.mjs [--root <dir>]... [--limit N] [--status archived|queued] [--dry-run] [--skip-links]"
  );
}

function main() {
  const config = loadConfig();
  const roots = getArgs("root");
  const selectedRoots = roots.length > 0 ? roots : getDefaultEpubRoots();
  const resolvedRoots = selectedRoots.map((root) => path.resolve(root));
  const limit = Number.parseInt(getArg("limit") || "0", 10);
  const dryRun = hasFlag("dry-run");
  const skipLinks = hasFlag("skip-links");
  const status = getArg("status") || "archived";

  const epubFiles = discoverEpubFiles(resolvedRoots);
  const artifacts = deduplicateEpubArtifacts(
    loadEpubArtifacts(epubFiles, {
      roots: resolvedRoots,
      machineRoot: config.machineRoot
    })
  );
  const selected =
    Number.isFinite(limit) && limit > 0 ? artifacts.slice(0, limit) : artifacts;

  if (selected.length === 0) {
    console.log("No EPUB files found under the requested roots.");
    return;
  }

  if (dryRun) {
    console.log(`Roots: ${resolvedRoots.join(" | ")}`);
    for (const artifact of selected) {
      console.log(`${artifact.title} <- ${artifact.filePath}`);
    }
    console.log(`\nDry run only. ${selected.length} EPUB file(s) matched.`);
    return;
  }

  const results = importEpubLibrary(config, selected, {
    status,
    allowFilesystemFallback: true,
    preferCli: true
  });

  console.log(`Imported EPUB index notes from: ${resolvedRoots.join(" | ")}`);
  for (const result of results) {
    console.log(`${result.action}: ${result.path} (mode: ${result.mode}) <- ${result.filePath}`);
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
