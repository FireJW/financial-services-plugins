import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const runtimeRoot = path.join(repoRoot, "vendor", "claude-code-recovered");
const cliPath = path.join(runtimeRoot, "dist", "cli.js");

test("recovered runtime renders help once built", (t) => {
  if (!existsSync(cliPath)) {
    t.skip("Runtime build missing. Run npm install && npm run build in vendor/claude-code-recovered first.");
    return;
  }

  const result = spawnSync("node", [cliPath, "--help"], {
    cwd: runtimeRoot,
    encoding: "utf8",
    timeout: 45_000,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /Claude Code/i);
});
