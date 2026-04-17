import {
  cliPath,
  ensureSuccessfulResult,
  getCandidatePluginDirs,
  getInitMessage,
  getResultMessage,
  parseNdjson,
  repoRoot,
  runRuntimeCli,
  runtimeRoot,
} from "./runtime-report-lib.mjs";

const requestedPluginDirs = process.argv.slice(2);
const pluginDirs = getCandidatePluginDirs(requestedPluginDirs);
const pluginArgs = pluginDirs.flatMap((pluginDir) => ["--plugin-dir", pluginDir]);

const command = [
  "node",
  cliPath,
  "--bare",
  "--strict-mcp-config",
  ...pluginArgs,
  "--print",
  "--verbose",
  "--output-format",
  "stream-json",
  "/cost",
];

const result = runRuntimeCli(command.slice(2), {
  cwd: repoRoot,
  timeout: 30_000,
});

ensureSuccessfulResult(result, "collect-runtime-init-report");

const messages = parseNdjson(result.stdout);
const initMessage = getInitMessage(messages);
const resultMessage = getResultMessage(messages);

if (!initMessage) {
  throw new Error("collect-runtime-init-report did not receive a system(init) message.");
}

const report = {
  generatedAt: new Date().toISOString(),
  runtimeRoot,
  cliPath,
  pluginDirs,
  command,
  status: result.status,
  signal: result.signal,
  stderr: result.stderr,
  init: initMessage ?? null,
  result: resultMessage ?? null,
  summary: {
    pluginCount: initMessage?.plugins?.length ?? 0,
    slashCommandCount: initMessage?.slash_commands?.length ?? 0,
    skillCount: initMessage?.skills?.length ?? 0,
  },
};

console.log(JSON.stringify(report, null, 2));
