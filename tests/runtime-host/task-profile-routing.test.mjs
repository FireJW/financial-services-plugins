import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const scriptPath = path.join(repoRoot, "scripts", "runtime", "run-task-profile.mjs");

test("task profile router lists the supported profiles", () => {
  const result = spawnSync("node", [scriptPath, "--list"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.deepEqual(
    result.stdout.trim().split(/\r?\n/),
    ["explore", "verifier", "worker"],
  );
});

test("task profile router exposes explore and verifier characteristics", () => {
  const exploreResult = spawnSync("node", [scriptPath, "--profile", "explore", "--json"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });
  const verifierResult = spawnSync("node", [scriptPath, "--profile", "verifier", "--json"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });

  assert.equal(exploreResult.status, 0, exploreResult.stderr || exploreResult.stdout);
  assert.equal(verifierResult.status, 0, verifierResult.stderr || verifierResult.stdout);

  const explore = JSON.parse(exploreResult.stdout);
  const verifier = JSON.parse(verifierResult.stdout);

  assert.equal(explore.modelTier, "economy");
  assert.equal(explore.requiresContract, false);
  assert.equal(verifier.verificationOnly, true);
  assert.equal(verifier.maxTurns, 4);
  assert.match(verifier.checklistPath, /docs[\\/]+runtime[\\/]+verification-checklist\.md$/);
});

test("task profile router builds a worker dry-run invocation with contract guidance", () => {
  const result = spawnSync(
    "node",
    [
      scriptPath,
      "--profile",
      "worker",
      "--dry-run",
      "--json",
      "--plugin-dir",
      "financial-analysis",
      "--",
      "--print",
      "/help",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);

  const preview = JSON.parse(result.stdout);
  assert.equal(preview.profile.name, "worker");
  assert.match(preview.profile.contractPath, /docs[\\/]+runtime[\\/]+sub-agent-contract\.md$/);
  assert.ok(
    preview.invocation.cliArgs.includes("--append-system-prompt-file"),
    result.stdout,
  );
  assert.ok(preview.invocation.cliArgs.includes("--print"), result.stdout);
  assert.ok(preview.invocation.cliArgs.includes("/help"), result.stdout);
});
