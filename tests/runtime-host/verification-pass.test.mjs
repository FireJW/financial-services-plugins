import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const scriptPath = path.join(repoRoot, "scripts", "runtime", "run-verification-pass.mjs");

test("verification pass succeeds for a valid worker output", () => {
  const inputPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "worker-output-valid.md",
  );
  const result = spawnSync("node", [scriptPath, "--input", inputPath, "--json"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);

  assert.equal(report.verdict, "PASS");
  assert.equal(report.ok, true);
});

test("verification pass fails for an invalid worker output", () => {
  const inputPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "worker-output-invalid.md",
  );
  const result = spawnSync("node", [scriptPath, "--input", inputPath, "--json"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });

  assert.equal(result.status, 1, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);

  assert.equal(report.verdict, "FAIL");
  assert.deepEqual(report.missingSections, ["Risks"]);
});

test("verification pass supports compaction mode text output", () => {
  const inputPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "compaction-summary-valid.md",
  );
  const result = spawnSync(
    "node",
    [scriptPath, "--input", inputPath, "--mode", "compaction", "--format", "text"],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /Verification mode: compaction/);
  assert.match(result.stdout, /VERDICT: PASS/);
});
