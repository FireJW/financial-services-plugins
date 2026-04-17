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

test("stream-json print mode requires --verbose", (t) => {
  if (!existsSync(cliPath)) {
    t.skip("Runtime build missing. Run npm install && npm run build in vendor/claude-code-recovered first.");
    return;
  }

  const result = spawnSync(
    "node",
    [
      cliPath,
      "--bare",
      "--strict-mcp-config",
      "--print",
      "--output-format",
      "stream-json",
      "/cost",
    ],
    {
      cwd: runtimeRoot,
      encoding: "utf8",
      timeout: 45_000,
    },
  );
 
  assert.equal(result.status, 1, result.stderr || result.stdout);
  assert.match(
    result.stderr,
    /--output-format=stream-json requires --verbose/i,
  );
});

test("stream-json print mode emits init and result messages for a local slash command", (t) => {
  if (!existsSync(cliPath)) {
    t.skip("Runtime build missing. Run npm install && npm run build in vendor/claude-code-recovered first.");
    return;
  }

  const result = spawnSync(
    "node",
    [
      cliPath,
      "--bare",
      "--strict-mcp-config",
      "--print",
      "--verbose",
      "--output-format",
      "stream-json",
      "/cost",
    ],
    {
      cwd: runtimeRoot,
      encoding: "utf8",
      timeout: 45_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);

  const messages = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));

  assert.ok(
    messages.some((message) => message.type === "system" && message.subtype === "init"),
    result.stdout,
  );
  assert.ok(
    messages.some((message) => message.type === "result"),
    result.stdout,
  );
  assert.match(
    messages.find((message) => message.type === "result")?.result ?? "",
    /Total cost:/i,
  );
});
