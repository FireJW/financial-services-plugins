import fs from "node:fs";
import path from "node:path";

import { repoRoot } from "./config/defaults.mjs";

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function parseFrontmatter(text) {
  if (!text.startsWith("---")) {
    return {};
  }

  const lines = text.split(/\r?\n/);
  const result = {};
  let index = 1;

  while (index < lines.length) {
    const line = lines[index];
    if (line.trim() === "---") {
      break;
    }

    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (match) {
      result[match[1]] = match[2].trim();
    }

    index += 1;
  }

  return result;
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function tokenize(value) {
  return normalize(value)
    .replace(/[^a-z0-9]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function matchesFilter(values, query) {
  const tokens = tokenize(query);
  if (tokens.length === 0) {
    return true;
  }

  return values.some((value) => {
    const haystack = tokenize(value);
    return tokens.every((token) => haystack.some((part) => part.includes(token)));
  });
}

function readCommandEntry(pluginId, pluginSource, filePath) {
  const text = readText(filePath);
  const frontmatter = parseFrontmatter(text);
  const bodySkillMatch = text.match(/Load the `([^`]+)` skill/i);

  return {
    name: path.basename(filePath, ".md"),
    description: frontmatter.description || "",
    argument_hint: frontmatter["argument-hint"] || "",
    command_path: path.relative(repoRoot, filePath).replaceAll("\\", "/"),
    referenced_skill: bodySkillMatch?.[1] || "",
    plugin_id: pluginId,
    plugin_source: pluginSource,
  };
}

function readSkillEntry(pluginId, pluginSource, filePath) {
  const text = readText(filePath);
  const frontmatter = parseFrontmatter(text);

  return {
    name: frontmatter.name || path.basename(path.dirname(filePath)),
    description: frontmatter.description || "",
    skill_path: path.relative(repoRoot, filePath).replaceAll("\\", "/"),
    plugin_id: pluginId,
    plugin_source: pluginSource,
  };
}

function collectPluginEntries(plugin) {
  const pluginRoot = path.join(repoRoot, plugin.source.replace(/^\.\//, ""));
  const commandsDir = path.join(pluginRoot, "commands");
  const skillsDir = path.join(pluginRoot, "skills");

  const commands = fs.existsSync(commandsDir)
    ? fs.readdirSync(commandsDir)
        .filter((name) => name.endsWith(".md"))
        .map((name) => readCommandEntry(plugin.name, plugin.source, path.join(commandsDir, name)))
        .sort((left, right) => left.name.localeCompare(right.name))
    : [];

  const skills = fs.existsSync(skillsDir)
    ? fs.readdirSync(skillsDir, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => path.join(skillsDir, entry.name, "SKILL.md"))
        .filter((filePath) => fs.existsSync(filePath))
        .map((filePath) => readSkillEntry(plugin.name, plugin.source, filePath))
        .sort((left, right) => left.name.localeCompare(right.name))
    : [];

  return {
    plugin_id: plugin.name,
    plugin_source: plugin.source,
    plugin_description: plugin.description || "",
    commands,
    skills,
  };
}

export function listPluginWorkflowCatalog({ pluginFilter = "", query = "" } = {}) {
  const marketplace = readJson(path.join(repoRoot, ".claude-plugin", "marketplace.json"));
  const normalizedPluginFilter = normalize(pluginFilter);

  const plugins = (marketplace.plugins || [])
    .filter((plugin) => {
      if (!normalizedPluginFilter) {
        return true;
      }

      return [plugin.name, plugin.source, plugin.description].some((value) =>
        normalize(value).includes(normalizedPluginFilter),
      );
    })
    .map(collectPluginEntries)
    .map((plugin) => {
      const commands = plugin.commands.filter((entry) =>
        matchesFilter(
          [entry.name, entry.description, entry.argument_hint, entry.referenced_skill],
          query,
        ),
      );
      const skills = plugin.skills.filter((entry) =>
        matchesFilter([entry.name, entry.description], query),
      );

      return {
        ...plugin,
        commands,
        skills,
      };
    })
    .filter((plugin) => plugin.commands.length > 0 || plugin.skills.length > 0)
    .sort((left, right) => left.plugin_id.localeCompare(right.plugin_id));

  const commandCount = plugins.reduce((sum, plugin) => sum + plugin.commands.length, 0);
  const skillCount = plugins.reduce((sum, plugin) => sum + plugin.skills.length, 0);

  return {
    plugin_filter: pluginFilter,
    query,
    plugin_count: plugins.length,
    command_count: commandCount,
    skill_count: skillCount,
    plugins,
  };
}
