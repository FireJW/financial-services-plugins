import { loadConfig } from "../src/config.mjs";
import { runObsidian } from "../src/obsidian-cli.mjs";

const config = loadConfig();
const commandArgs = process.argv.slice(2);

if (commandArgs.length === 0) {
  console.error("Usage: node scripts/obsidian.mjs <command> [args]");
  process.exit(1);
}

const result = runObsidian(config, commandArgs);
if (result.stdout) {
  process.stdout.write(result.stdout);
}
if (result.stderr) {
  process.stderr.write(result.stderr);
}

