import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CONFIG_DIR = path.join(ROOT, "config");
const DEFAULT_CONFIG_PATH = path.join(CONFIG_DIR, "vault.local.json");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function assertString(value, label) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Missing required config field: ${label}`);
  }
}

export function getProjectRoot() {
  return ROOT;
}

export function getDefaultConfigPath() {
  return DEFAULT_CONFIG_PATH;
}

export function loadConfig(configPath = DEFAULT_CONFIG_PATH) {
  if (!fs.existsSync(configPath)) {
    throw new Error(`Missing config file: ${configPath}`);
  }

  const config = readJson(configPath);
  assertString(config.vaultPath, "vaultPath");
  assertString(config.vaultName, "vaultName");
  assertString(config.machineRoot, "machineRoot");

  const cliCandidates = config.obsidian?.cliCandidates ?? [];
  const exeCandidates = config.obsidian?.exeCandidates ?? [];
  if (!Array.isArray(cliCandidates) || !Array.isArray(exeCandidates)) {
    throw new Error("Config field obsidian.cliCandidates/exeCandidates must be arrays.");
  }

  return {
    ...config,
    configPath,
    projectRoot: ROOT,
    obsidian: {
      cliCandidates,
      exeCandidates
    }
  };
}
