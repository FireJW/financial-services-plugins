import fs from "node:fs";
import path from "node:path";
import { runObsidian } from "./obsidian-cli.mjs";
import { assertWithinBoundary } from "./boundary.mjs";

export function ensureVaultDirectory(config, relativeDir) {
  assertWithinBoundary(relativeDir, config.machineRoot);
  fs.mkdirSync(path.join(config.vaultPath, relativeDir), { recursive: true });
}

export function writeNote(config, note, options = {}) {
  assertWithinBoundary(note.path, config.machineRoot);

  const allowFilesystemFallback = options.allowFilesystemFallback === true;
  const preferCli = options.preferCli !== false;

  if (preferCli) {
    try {
      runObsidian(config, [
        "create",
        `path=${note.path}`,
        `content=${note.content}`,
        "overwrite"
      ]);
      return { mode: "cli", path: note.path };
    } catch (error) {
      if (!allowFilesystemFallback) {
        throw error;
      }
    }
  }

  const target = path.join(config.vaultPath, note.path);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, note.content, "utf8");
  return { mode: "filesystem-fallback", path: note.path };
}
