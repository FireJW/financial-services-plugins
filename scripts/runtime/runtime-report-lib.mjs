import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const repoRoot = path.resolve(__dirname, "..", "..");
export const runtimeRoot = path.join(repoRoot, "vendor", "claude-code-recovered");
export const cliPath = path.join(runtimeRoot, "dist", "cli.js");

const DEFAULT_PLUGIN_DIR_NAMES = [
  "financial-analysis",
  "equity-research",
  "investment-banking",
];

const MANIFEST_RELATIVE_PATHS = [
  path.join(".claude-plugin", "plugin.json"),
  path.join(".Codex-plugin", "plugin.json"),
];

export const FILESYSTEM_INVENTORY_RULES = {
  commandGlob: "<plugin>/commands/*.md",
  skillGlob: "<plugin>/skills/*/SKILL.md",
  excludedAssetKinds: [
    "skills/*/references/**",
    "skills/*/reference/**",
    "skills/*/assets/**",
    "skills/*/scripts/**",
    "skills/*/examples/**",
    "skills/*/tests/**",
    "skills/*/sample-pool/**",
    "skills/*/cases/**",
    "skills/*/LICENSE*",
    "skills/*/README*",
    "skills/*/TROUBLESHOOTING*",
  ],
};

export function getCandidatePluginDirs(requestedPluginDirs = []) {
  const candidates =
    requestedPluginDirs.length > 0
      ? requestedPluginDirs
      : DEFAULT_PLUGIN_DIR_NAMES.map((name) => path.join(repoRoot, name));

  return candidates
    .map((pluginDir) => path.resolve(pluginDir))
    .filter((pluginDir, index, allDirs) => existsSync(pluginDir) && allDirs.indexOf(pluginDir) === index);
}

export function toPluginArgs(pluginDirs) {
  return pluginDirs.flatMap((pluginDir) => ["--plugin-dir", pluginDir]);
}

export function runRuntimeCli(args, options = {}) {
  if (!existsSync(cliPath)) {
    throw new Error(`Recovered runtime is not built yet. Expected: ${cliPath}`);
  }

  const result = spawnSync("node", [cliPath, ...args], {
    cwd: options.cwd ?? repoRoot,
    encoding: "utf8",
    timeout: options.timeout ?? 30_000,
    maxBuffer: options.maxBuffer ?? 16 * 1024 * 1024,
    input: options.input,
    env: {
      ...process.env,
      ...(options.env ?? {}),
    },
  });

  if (result.error) {
    throw new Error(`Failed to run runtime CLI: ${result.error.message}`);
  }

  return result;
}

export function writeRuntimeOutputFile(outputPath, content) {
  if (!outputPath) {
    return;
  }

  writeFileSync(outputPath, content ?? "", "utf8");
}

export function ensureSuccessfulResult(result, label) {
  if (result.status === 0) {
    return;
  }

  const message = [
    `${label} failed.`,
    `status=${result.status}`,
    result.signal ? `signal=${result.signal}` : null,
    result.stderr?.trim() ? `stderr=${result.stderr.trim()}` : null,
    result.stdout?.trim() ? `stdout=${result.stdout.trim()}` : null,
  ]
    .filter(Boolean)
    .join("\n");

  throw new Error(message);
}

export function parseNdjson(stdout = "") {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

export function getInitMessage(messages) {
  return messages.find((message) => message.type === "system" && message.subtype === "init") ?? null;
}

export function getResultMessage(messages) {
  return messages.find((message) => message.type === "result") ?? null;
}

export function collectFilesystemInventory(pluginDirs) {
  const plugins = pluginDirs.map((pluginDir) => {
    const manifest = readPluginManifest(pluginDir);
    const pluginName = manifest?.data?.name ?? path.basename(pluginDir);

    const commands = collectCommands(pluginDir, pluginName);
    const skills = collectSkills(pluginDir, pluginName);

    return {
      name: pluginName,
      path: pluginDir,
      manifestPath: manifest?.path ?? null,
      commands,
      skills,
      toolEligibleSkills: skills.filter((skill) => skill.toolEligible),
    };
  });

  return {
    plugins,
    summary: {
      pluginCount: plugins.length,
      commandCount: plugins.reduce((sum, plugin) => sum + plugin.commands.length, 0),
      skillCount: plugins.reduce((sum, plugin) => sum + plugin.skills.length, 0),
      toolEligibleSkillCount: plugins.reduce(
        (sum, plugin) => sum + plugin.toolEligibleSkills.length,
        0,
      ),
    },
    rules: FILESYSTEM_INVENTORY_RULES,
  };
}

export function collectRuntimePluginSurface(initMessage, pluginNames) {
  const pluginSet = new Set(pluginNames);
  const plugins = (initMessage?.plugins ?? [])
    .filter((plugin) => plugin?.name && pluginSet.has(plugin.name))
    .sort((left, right) => left.name.localeCompare(right.name));
  const slashCommands = normalizeQualifiedEntries(initMessage?.slash_commands ?? [], pluginSet);
  const skills = normalizeQualifiedEntries(initMessage?.skills ?? [], pluginSet);

  return {
    plugins,
    slashCommands,
    skills,
    summary: {
      pluginCount: plugins.length,
      slashCommandCount: slashCommands.length,
      skillCount: skills.length,
    },
  };
}

export function diffSimpleValues(expectedValues, actualValues) {
  const expected = new Set(expectedValues);
  const actual = new Set(actualValues);

  return {
    missingInRuntime: [...expected].filter((value) => !actual.has(value)).sort(),
    extraInRuntime: [...actual].filter((value) => !expected.has(value)).sort(),
  };
}

export function diffQualifiedEntries(expectedEntries, actualEntries) {
  return diffSimpleValues(
    expectedEntries.map((entry) => entry.qualifiedName),
    actualEntries.map((entry) => entry.qualifiedName),
  );
}

function collectCommands(pluginDir, pluginName) {
  const commandsDir = path.join(pluginDir, "commands");

  if (!existsSync(commandsDir)) {
    return [];
  }

  return readdirSync(commandsDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
    .map((entry) => entry.name)
    .sort((left, right) => left.localeCompare(right))
    .map((fileName) => {
      const name = path.basename(fileName, ".md");

      return {
        name,
        qualifiedName: `${pluginName}:${name}`,
        path: path.join(commandsDir, fileName),
      };
    });
}

function collectSkills(pluginDir, pluginName) {
  const skillsDir = path.join(pluginDir, "skills");

  if (!existsSync(skillsDir)) {
    return [];
  }

  return readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const skillPath = path.join(skillsDir, entry.name, "SKILL.md");

      if (!existsSync(skillPath)) {
        return null;
      }

      return {
        name: entry.name,
        qualifiedName: `${pluginName}:${entry.name}`,
        path: skillPath,
        toolEligible: isToolEligibleSkill(skillPath),
      };
    })
    .filter(Boolean)
    .sort((left, right) => left.name.localeCompare(right.name));
}

function normalizeQualifiedEntries(entries, pluginSet) {
  return entries
    .filter((entry) => typeof entry === "string")
    .map(parseQualifiedEntry)
    .filter((entry) => entry && pluginSet.has(entry.pluginName))
    .sort((left, right) => left.qualifiedName.localeCompare(right.qualifiedName));
}

function parseQualifiedEntry(value) {
  const separatorIndex = value.indexOf(":");

  if (separatorIndex <= 0 || separatorIndex === value.length - 1) {
    return null;
  }

  const pluginName = value.slice(0, separatorIndex);
  const name = value.slice(separatorIndex + 1);

  return {
    pluginName,
    name,
    qualifiedName: value,
  };
}

function readPluginManifest(pluginDir) {
  const manifestPath = MANIFEST_RELATIVE_PATHS.map((relativePath) => path.join(pluginDir, relativePath)).find(
    (candidatePath) => existsSync(candidatePath),
  );

  if (!manifestPath) {
    return null;
  }

  return {
    path: manifestPath,
    data: JSON.parse(readFileSync(manifestPath, "utf8")),
  };
}

function isToolEligibleSkill(skillPath) {
  const frontmatterBlock = readFrontmatterBlock(skillPath);
  if (!frontmatterBlock) {
    return false;
  }

  return /^(description|when_to_use):\s+/m.test(frontmatterBlock);
}

function readFrontmatterBlock(filePath) {
  const content = readFileSync(filePath, "utf8");

  if (!content.startsWith("---")) {
    return null;
  }

  const closingIndex = content.indexOf("\n---", 3);
  if (closingIndex === -1) {
    return null;
  }

  return content.slice(4, closingIndex);
}
