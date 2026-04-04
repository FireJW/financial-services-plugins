import { spawnSync } from "node:child_process";
import fs from "node:fs";

function firstConfiguredCandidate(candidates) {
  return candidates.find(
    (candidate) => typeof candidate === "string" && candidate.trim() !== ""
  ) ?? null;
}

function commandExists(command) {
  const result = spawnSync("cmd", ["/c", "where", command], { encoding: "utf8" });
  return result.status === 0;
}

function chooseCliCandidate(config) {
  for (const candidate of config.obsidian.cliCandidates) {
    if (candidate.includes("\\") || candidate.includes("/")) {
      if (fs.existsSync(candidate)) {
        return candidate;
      }
      continue;
    }
    if (commandExists(candidate)) {
      return candidate;
    }
  }
  return null;
}

function chooseExeCandidate(config) {
  for (const candidate of config.obsidian.exeCandidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  // Sandboxed runtimes can hide AppData installs from fs.existsSync even when
  // the configured path is correct on the host machine.
  return firstConfiguredCandidate(config.obsidian.exeCandidates);
}

export function resolveObsidianEnvironment(config) {
  return {
    cliCommand: chooseCliCandidate(config),
    exePath: chooseExeCandidate(config)
  };
}

export function buildObsidianArgs(config, commandArgs) {
  return [`vault=${config.vaultName}`, ...commandArgs];
}

export function runObsidian(config, commandArgs, options = {}) {
  const env = resolveObsidianEnvironment(config);
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
