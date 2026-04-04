import { loadConfig } from "../src/config.mjs";
import { runObsidian } from "../src/obsidian-cli.mjs";

const config = loadConfig();
const stamp = new Date().toISOString();
const pathArg = `${config.machineRoot}/90-ops/logs/smoke-${stamp.slice(0, 10)}.md`;
const content = `# Obsidian CLI Smoke

- time: ${stamp}
- writer: codex
- target: ${config.machineRoot}
`;

runObsidian(config, [
  "create",
  `path=${pathArg}`,
  `content=${content}`,
  "overwrite"
]);

runObsidian(config, [
  "append",
  `path=${pathArg}`,
  'content=\n- append_check: ok'
]);

console.log(`Smoke note written: ${pathArg}`);

