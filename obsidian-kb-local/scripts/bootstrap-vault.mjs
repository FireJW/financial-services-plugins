import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { buildBootstrapPlan } from "../src/bootstrap-plan.mjs";
import { ensureVaultDirectory, writeNote } from "../src/note-writer.mjs";

const config = loadConfig();
const plan = buildBootstrapPlan(config);
const allowFilesystemFallback = process.argv.includes("--filesystem-fallback");

for (const dir of plan.directories) {
  ensureVaultDirectory(config, dir);
}

for (const note of plan.notes) {
  const result = writeNote(config, note, {
    allowFilesystemFallback,
    preferCli: !allowFilesystemFallback
  });
  console.log(`Wrote ${note.path} via ${result.mode}`);
}

console.log("\nBootstrap completed.");
