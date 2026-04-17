import {
  cliPath,
  ensureSuccessfulResult,
  getCandidatePluginDirs,
  repoRoot,
  runRuntimeCli,
  runtimeRoot,
  toPluginArgs,
} from "./runtime-report-lib.mjs";

const requestedPluginDirs = process.argv.slice(2);
const pluginDirs = getCandidatePluginDirs(requestedPluginDirs);
const pluginArgs = toPluginArgs(pluginDirs);

const result = runRuntimeCli([...pluginArgs, "plugin", "list"], {
  cwd: runtimeRoot,
  timeout: 30_000,
});

ensureSuccessfulResult(result, "collect-runtime-compat-report");

const report = {
  generatedAt: new Date().toISOString(),
  runtimeRoot,
  cliPath,
  pluginDirs,
  command: ["node", cliPath, ...pluginArgs, "plugin", "list"],
  status: result.status,
  signal: result.signal,
  stdout: result.stdout,
  stderr: result.stderr,
  plugins: parsePluginList(result.stdout),
};

report.summary = {
  discovered: report.plugins.length,
  loaded: report.plugins.filter((plugin) => /loaded$/i.test(plugin.status)).length,
  loadedWithErrors: report.plugins.filter((plugin) =>
    /loaded with errors/i.test(plugin.status),
  ).length,
};

console.log(JSON.stringify(report, null, 2));

function parsePluginList(stdout) {
  if (!stdout.includes("Session-only plugins (--plugin-dir):")) {
    return [];
  }

  const blocks = stdout
    .split(/\r?\n(?=\s{2}>\s)/)
    .map((block) => block.trim())
    .filter((block) => block.startsWith("> "));

  return blocks.map((block) => {
    const source = capture(block, /^>\s+(.+)$/m);
    const version = capture(block, /^\s*Version:\s+(.+)$/m);
    const pluginPath = capture(block, /^\s*Path:\s+(.+)$/m);
    const status = capture(block, /^\s*Status:\s+(.+)$/m);
    const errorLines = block
      .split(/\r?\n/)
      .filter((line) => /^\s*Error:\s+/.test(line))
      .map((line) => line.replace(/^\s*Error:\s+/, ""));

    return {
      source,
      version,
      path: pluginPath,
      status,
      errors: errorLines,
      rawBlock: block,
    };
  });
}

function capture(text, pattern) {
  return text.match(pattern)?.[1] ?? "";
}
