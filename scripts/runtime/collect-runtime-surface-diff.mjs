import {
  cliPath,
  collectFilesystemInventory,
  collectRuntimePluginSurface,
  diffQualifiedEntries,
  diffSimpleValues,
  ensureSuccessfulResult,
  getCandidatePluginDirs,
  getInitMessage,
  getResultMessage,
  parseNdjson,
  repoRoot,
  runRuntimeCli,
  runtimeRoot,
  toPluginArgs,
} from "./runtime-report-lib.mjs";

const requestedPluginDirs = process.argv.slice(2);
const pluginDirs = getCandidatePluginDirs(requestedPluginDirs);
const pluginArgs = toPluginArgs(pluginDirs);
const filesystem = collectFilesystemInventory(pluginDirs);
const pluginNames = filesystem.plugins.map((plugin) => plugin.name);

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

ensureSuccessfulResult(result, "collect-runtime-surface-diff");

const messages = parseNdjson(result.stdout);
const initMessage = getInitMessage(messages);
const resultMessage = getResultMessage(messages);

if (!initMessage) {
  throw new Error("collect-runtime-surface-diff did not receive a system(init) message.");
}

const runtime = collectRuntimePluginSurface(initMessage, pluginNames);
const filesystemCommands = filesystem.plugins.flatMap((plugin) => plugin.commands);
const filesystemSkills = filesystem.plugins.flatMap((plugin) => plugin.skills);
const filesystemToolEligibleSkills = filesystem.plugins.flatMap(
  (plugin) => plugin.toolEligibleSkills,
);
const filesystemSlashQualifiedNames = [
  ...filesystemCommands.map((entry) => entry.qualifiedName),
  ...filesystemSkills.map((entry) => entry.qualifiedName),
];
const runtimeSlashQualifiedNames = runtime.slashCommands.map((entry) => entry.qualifiedName);
const runtimeSkillQualifiedNames = runtime.skills.map((entry) => entry.qualifiedName);
const pluginDiff = diffSimpleValues(
  filesystem.plugins.map((plugin) => plugin.name),
  runtime.plugins.map((plugin) => plugin.name),
);
const commandSlashDiff = diffQualifiedEntries(filesystemCommands, runtime.slashCommands);
const skillSlashDiff = diffQualifiedEntries(filesystemSkills, runtime.slashCommands);
const skillRuntimeDiff = diffQualifiedEntries(filesystemToolEligibleSkills, runtime.skills);
const runtimeSlashBackingDiff = diffSimpleValues(
  filesystemSlashQualifiedNames,
  runtimeSlashQualifiedNames,
);
const runtimeSkillBackingDiff = diffSimpleValues(
  filesystemToolEligibleSkills.map((entry) => entry.qualifiedName),
  runtimeSkillQualifiedNames,
);

const diff = {
  filesystemPluginsMissingFromRuntimePlugins: pluginDiff.missingInRuntime,
  runtimePluginsWithoutFilesystemRoot: pluginDiff.extraInRuntime,
  commandsMissingFromRuntimeSlash: commandSlashDiff.missingInRuntime,
  skillsMissingFromRuntimeSlash: skillSlashDiff.missingInRuntime,
  skillsMissingFromRuntimeSkills: skillRuntimeDiff.missingInRuntime,
  runtimeSlashWithoutFilesystemBacking: runtimeSlashBackingDiff.extraInRuntime,
  runtimeSkillsWithoutFilesystemBacking: runtimeSkillBackingDiff.extraInRuntime,
};

const byPlugin = Object.fromEntries(
  filesystem.plugins.map((plugin) => {
    const filesystemCommandNames = new Set(
      plugin.commands.map((entry) => entry.qualifiedName),
    );
    const filesystemSkillNames = new Set(
      plugin.skills.map((entry) => entry.qualifiedName),
    );
    const filesystemToolEligibleSkillNames = new Set(
      plugin.toolEligibleSkills.map((entry) => entry.qualifiedName),
    );
    const runtimePluginSlashEntries = runtime.slashCommands.filter(
      (entry) => entry.pluginName === plugin.name,
    );
    const runtimePluginSkillEntries = runtime.skills.filter(
      (entry) => entry.pluginName === plugin.name,
    );

    return [
      plugin.name,
      {
        filesystemCommandCount: plugin.commands.length,
        filesystemSkillCount: plugin.skills.length,
        filesystemToolEligibleSkillCount: plugin.toolEligibleSkills.length,
        runtimeSlashCommandCount: runtimePluginSlashEntries.filter((entry) =>
          filesystemCommandNames.has(entry.qualifiedName),
        ).length,
        runtimeSlashSkillCount: runtimePluginSlashEntries.filter((entry) =>
          filesystemSkillNames.has(entry.qualifiedName),
        ).length,
        runtimeSlashExtraCount: runtimePluginSlashEntries.filter(
          (entry) =>
            !filesystemCommandNames.has(entry.qualifiedName) &&
            !filesystemSkillNames.has(entry.qualifiedName),
        ).length,
        runtimeSkillCount: runtimePluginSkillEntries.length,
        commandsMissingFromRuntimeSlash: diffSimpleValues(
          plugin.commands.map((entry) => entry.qualifiedName),
          runtimePluginSlashEntries.map((entry) => entry.qualifiedName),
        ).missingInRuntime,
        skillsMissingFromRuntimeSlash: diffSimpleValues(
          plugin.skills.map((entry) => entry.qualifiedName),
          runtimePluginSlashEntries.map((entry) => entry.qualifiedName),
        ).missingInRuntime,
        skillsMissingFromRuntimeSkills: diffSimpleValues(
          plugin.toolEligibleSkills.map((entry) => entry.qualifiedName),
          runtimePluginSkillEntries.map((entry) => entry.qualifiedName),
        ).missingInRuntime,
      },
    ];
  }),
);

const report = {
  generatedAt: new Date().toISOString(),
  runtimeRoot,
  cliPath,
  pluginDirs,
  command,
  status: result.status,
  signal: result.signal,
  stderr: result.stderr,
  filesystem,
  runtime: {
    init: initMessage,
    result: resultMessage ?? null,
    plugins: runtime.plugins,
    slashCommands: runtime.slashCommands,
    skills: runtime.skills,
    summary: runtime.summary,
  },
  diff,
  byPlugin,
  summary: {
    pluginCount: filesystem.summary.pluginCount,
    filesystemCommandCount: filesystem.summary.commandCount,
    filesystemSkillCount: filesystem.summary.skillCount,
    filesystemToolEligibleSkillCount: filesystem.summary.toolEligibleSkillCount,
    runtimePluginCount: runtime.summary.pluginCount,
    runtimeSlashCount: runtime.summary.slashCommandCount,
    runtimeSkillCount: runtime.summary.skillCount,
    missingCount:
      diff.filesystemPluginsMissingFromRuntimePlugins.length +
      diff.commandsMissingFromRuntimeSlash.length +
      diff.skillsMissingFromRuntimeSlash.length +
      diff.skillsMissingFromRuntimeSkills.length,
    unexpectedCount:
      diff.runtimePluginsWithoutFilesystemRoot.length +
      diff.runtimeSlashWithoutFilesystemBacking.length +
      diff.runtimeSkillsWithoutFilesystemBacking.length,
  },
};

console.log(JSON.stringify(report, null, 2));
