import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const COMMON_OBSIDIAN_COMMANDS = [
  "obsidian",
  "Obsidian",
  "obsidian.exe",
  "Obsidian.exe",
  "obsidian.com",
  "Obsidian.com"
];

const COMMON_OBSIDIAN_EXECUTABLES = [
  "Obsidian.exe",
  "obsidian.exe",
  "Obsidian.com",
  "obsidian.com"
];

function firstConfiguredCandidate(candidates) {
  return candidates.find(
    (candidate) => typeof candidate === "string" && candidate.trim() !== ""
  ) ?? null;
}

function commandExists(command, options = {}) {
  const injectedCommandExists = options.commandExists;
  if (typeof injectedCommandExists === "function") {
    return injectedCommandExists(command);
  }

  const result = spawnSync("cmd", ["/c", "where", command], { encoding: "utf8" });
  return result.status === 0;
}

function pathExists(candidate, options = {}) {
  const injectedPathExists = options.pathExists;
  if (typeof injectedPathExists === "function") {
    return injectedPathExists(candidate);
  }

  try {
    return fs.existsSync(candidate);
  } catch {
    return false;
  }
}

function uniqueStrings(values) {
  return [...new Set(values.filter((value) => typeof value === "string" && value.trim() !== ""))];
}

function looksLikePath(candidate) {
  return (
    typeof candidate === "string" &&
    (candidate.includes("\\") || candidate.includes("/") || /^[A-Za-z]:/.test(candidate))
  );
}

function splitPathEntries(rawPath) {
  return String(rawPath ?? "")
    .split(";")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function inferInstallPathCandidates(options = {}) {
  const env = options.env ?? process.env;
  const pathEntries = splitPathEntries(env.Path ?? env.PATH);
  const candidates = [];

  for (const entry of pathEntries) {
    if (path.basename(entry).toLowerCase() !== "obsidian") {
      continue;
    }

    for (const executable of COMMON_OBSIDIAN_EXECUTABLES) {
      candidates.push(path.join(entry, executable));
    }
  }

  return uniqueStrings(candidates);
}

function normalizePath(candidate) {
  return typeof candidate === "string" ? candidate.replace(/\//g, "\\").toLowerCase() : "";
}

function samePath(left, right) {
  return normalizePath(left) !== "" && normalizePath(left) === normalizePath(right);
}

function chooseCliCandidate(config, options = {}) {
  const configuredCandidates = Array.isArray(config.obsidian?.cliCandidates)
    ? config.obsidian.cliCandidates
    : [];
  const configuredExeCandidates = Array.isArray(config.obsidian?.exeCandidates)
    ? config.obsidian.exeCandidates
    : [];
  const fallbackPathCandidates = [];

  for (const candidate of uniqueStrings([...configuredCandidates, ...COMMON_OBSIDIAN_COMMANDS])) {
    if (looksLikePath(candidate)) {
      if (pathExists(candidate, options)) {
        return candidate;
      }
      fallbackPathCandidates.push(candidate);
      continue;
    }

    if (commandExists(candidate, options)) {
      return candidate;
    }
  }

  for (const candidate of uniqueStrings([
    ...inferInstallPathCandidates(options),
    ...configuredExeCandidates
  ])) {
    if (pathExists(candidate, options)) {
      return candidate;
    }
    fallbackPathCandidates.push(candidate);
  }

  return firstConfiguredCandidate(fallbackPathCandidates);
}

function chooseExeCandidate(config, options = {}) {
  const configuredCandidates = Array.isArray(config.obsidian?.exeCandidates)
    ? config.obsidian.exeCandidates
    : [];
  const inferredCandidates = inferInstallPathCandidates(options);

  for (const candidate of uniqueStrings([...configuredCandidates, ...inferredCandidates])) {
    if (pathExists(candidate, options)) {
      return candidate;
    }
  }

  // Sandboxed runtimes can hide AppData installs from fs.existsSync even when
  // the configured path is correct on the host machine.
  return firstConfiguredCandidate([...configuredCandidates, ...inferredCandidates]);
}

function resolveCliMode(cliCommand, exePath) {
  if (!cliCommand) {
    return null;
  }

  if (!looksLikePath(cliCommand)) {
    return "registered-command";
  }

  if (samePath(cliCommand, exePath)) {
    return "desktop-executable";
  }

  if (/\.com$/i.test(cliCommand)) {
    return "registered-shim";
  }

  return "path-candidate";
}

export function resolveObsidianEnvironment(config, options = {}) {
  const exePath = chooseExeCandidate(config, options);
  const cliCommand = chooseCliCandidate(config, options);

  return {
    cliCommand,
    exePath,
    cliMode: resolveCliMode(cliCommand, exePath)
  };
}

export function buildObsidianArgs(config, commandArgs) {
  return [`vault=${config.vaultName}`, ...commandArgs];
}

export function runObsidian(config, commandArgs, options = {}) {
  const env = resolveObsidianEnvironment(config, options);
  if (!env.cliCommand) {
    const exeHint = env.exePath
      ? `Detected desktop app at ${env.exePath}, but CLI is not registered yet.`
      : "Desktop app path was not detected from configured candidates.";
    throw new Error(
      `Obsidian CLI not found. ${exeHint} Enable 'Command line interface' in Obsidian first.`
    );
  }

  const args = buildObsidianArgs(config, commandArgs);
  const result = spawnSync(env.cliCommand, args, {
    encoding: "utf8",
    stdio: options.stdio ?? "pipe"
  });

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    const stderr = (result.stderr || "").trim();
    const stdout = (result.stdout || "").trim();
    throw new Error(`Obsidian CLI failed: ${stderr || stdout || "unknown error"}`);
  }

  return result;
}
