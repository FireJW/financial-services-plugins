import { loadConfig } from "../src/config.mjs";
import { rebuildAutomaticLinks } from "../src/link-graph.mjs";

const args = process.argv.slice(2);

function getArg(name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }

  return args[index + 1];
}

function main() {
  const maxLinks = Number.parseInt(getArg("max-links") || "8", 10);
  const minScore = Number.parseInt(getArg("min-score") || "4", 10);
  const config = loadConfig();
  const result = rebuildAutomaticLinks(config, {
    maxLinks,
    minScore,
    allowFilesystemFallback: true,
    preferCli: true
  });

  console.log(`Scanned: ${result.scanned}`);
  console.log(`Updated: ${result.updated}`);
  for (const entry of result.results) {
    console.log(`- ${entry.path} (${entry.relatedCount} links, ${entry.mode})`);
  }
}

main();
