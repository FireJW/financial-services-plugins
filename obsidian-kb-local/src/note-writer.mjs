import fs from "node:fs";
import path from "node:path";
import { resolveObsidianEnvironment, runObsidian } from "./obsidian-cli.mjs";
import { assertWithinBoundary } from "./boundary.mjs";

const DEFAULT_CLI_VERIFY_TIMEOUT_MS = 1500;
const DEFAULT_CLI_RUN_TIMEOUT_MS = 8000;
const CLI_VERIFY_INTERVAL_MS = 50;

export function ensureVaultDirectory(config, relativeDir) {
  assertWithinBoundary(relativeDir, config.machineRoot);
  fs.mkdirSync(path.join(config.vaultPath, relativeDir), { recursive: true });
}

export function writeNote(config, note, options = {}) {
  assertWithinBoundary(note.path, config.machineRoot);

  const allowFilesystemFallback = options.allowFilesystemFallback === true;
  const forceCli = options.forceCli === true;
  const preferCli = forceCli || options.preferCli !== false;
  const target = path.join(config.vaultPath, note.path);
  const runCli = options.runObsidian || runObsidian;
  const resolveCliEnvironment =
    options.resolveObsidianEnvironment || resolveObsidianEnvironment;
  const cliVerifyTimeoutMs =
    Number.isFinite(options.cliVerifyTimeoutMs) && options.cliVerifyTimeoutMs >= 0
      ? options.cliVerifyTimeoutMs
      : DEFAULT_CLI_VERIFY_TIMEOUT_MS;
  const cliRunTimeoutMs =
    Number.isFinite(options.cliRunTimeoutMs) && options.cliRunTimeoutMs >= 0
      ? options.cliRunTimeoutMs
      : DEFAULT_CLI_RUN_TIMEOUT_MS;
  const cliEnvironment = preferCli ? resolveCliEnvironment(config, options) : null;
  const cliWouldLaunchDesktop =
    cliEnvironment?.cliMode === "desktop-executable" ||
    cliEnvironment?.cliMode === "path-candidate" ||
    (cliEnvironment?.appRunning === false &&
      (cliEnvironment?.cliMode === "registered-command" ||
        cliEnvironment?.cliMode === "registered-shim"));

  let cliAttempted = false;
  let cliError = null;

  if (preferCli && !(allowFilesystemFallback && cliWouldLaunchDesktop)) {
    try {
      cliAttempted = true;
      runCli(
        config,
        [
          "create",
          `path=${note.path}`,
          `content=${note.content}`,
          "overwrite"
        ],
        {
          stdio: "ignore",
          timeoutMs: cliRunTimeoutMs
        }
      );

      if (!waitForExpectedNote(target, note.content, cliVerifyTimeoutMs)) {
        throw new Error(`Obsidian CLI returned success but note was not written: ${note.path}`);
      }

      return { mode: "cli", path: note.path };
    } catch (error) {
      cliError = error;
      if (!allowFilesystemFallback) {
        throw error;
      }
    }
  }

  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, note.content, "utf8");
  return {
    mode: "filesystem-fallback",
    path: note.path,
    cliAttempted,
    cliErrorCode: cliError?.code ?? null,
    cliErrorMessage: cliError?.message ?? null
  };
}

function waitForExpectedNote(target, expectedContent, timeoutMs) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() <= deadline) {
    if (noteContentMatches(target, expectedContent)) {
      return true;
    }

    sleep(CLI_VERIFY_INTERVAL_MS);
  }

  return noteContentMatches(target, expectedContent);
}

function noteContentMatches(target, expectedContent) {
  try {
    return fs.existsSync(target) && fs.readFileSync(target, "utf8") === expectedContent;
  } catch {
    return false;
  }
}

function sleep(durationMs) {
  const end = Date.now() + durationMs;
  while (Date.now() < end) {
    // Busy wait is acceptable here because verification windows are short and synchronous.
  }
}
