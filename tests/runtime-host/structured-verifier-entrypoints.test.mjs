import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const verifierScript = path.join(repoRoot, "scripts", "runtime", "run-verifier-task.mjs");
const verificationPassScript = path.join(
  repoRoot,
  "scripts",
  "runtime",
  "run-verification-pass.mjs",
);

test("structured verifier dry-run advertises structured mode and output path", () => {
  const result = spawnSync(
    "node",
    [
      verifierScript,
      "--original-task-file",
      "tests/fixtures/runtime-entrypoints/verifier-original-task.md",
      "--worker-output-file",
      "tests/fixtures/runtime-orchestration/worker-output-valid.md",
      "--files-changed-file",
      "tests/fixtures/runtime-entrypoints/files-changed.txt",
      "--approach-file",
      "tests/fixtures/runtime-entrypoints/verifier-approach.md",
      "--structured-verifier",
      "--structured-output-file",
      "runtime-state/test-structured-verifier.json",
      "--dry-run",
      "--json",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.profile.name, "verifier");
  assert.equal(payload.structuredVerifier, true);
  assert.match(payload.prompt, /Return JSON only/);
  assert.match(payload.prompt, /schemaVersion = "structured-verifier-v1"/);
  assert.match(payload.structuredOutputPath, /test-structured-verifier\.json$/);
});

test("structured verifier local-only mode preserves structured metadata", () => {
  const result = spawnSync(
    "node",
    [
      verifierScript,
      "--original-task-file",
      "tests/fixtures/runtime-entrypoints/verifier-original-task.md",
      "--worker-output-file",
      "tests/fixtures/runtime-orchestration/worker-output-valid.md",
      "--structured-verifier",
      "--structured-output-file",
      "runtime-state/test-structured-local-only.json",
      "--local-only",
      "--json",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.mode, "local-only");
  assert.equal(payload.preflight.ok, true);
  assert.equal(payload.structuredVerifier, true);
  assert.match(payload.structuredOutputPath, /test-structured-local-only\.json$/);
});

test("verification pass supports structured-verifier mode in json output", () => {
  const result = spawnSync(
    "node",
    [
      verificationPassScript,
      "--input",
      "tests/fixtures/runtime-orchestration/structured-verifier-valid.json",
      "--mode",
      "structured-verifier",
      "--json",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);

  assert.equal(report.ok, true, result.stdout);
  assert.equal(report.verdict, "PASS");
  assert.equal(report.hasAdversarialProbe, true);
});

test("verification pass fails closed for an invalid structured verifier artifact", () => {
  const result = spawnSync(
    "node",
    [
      verificationPassScript,
      "--input",
      "tests/fixtures/runtime-orchestration/structured-verifier-invalid-missing-check-field.json",
      "--mode",
      "structured-verifier",
      "--format",
      "text",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 1, result.stderr || result.stdout);
  assert.match(result.stdout, /Verification mode: structured-verifier/);
  assert.match(result.stdout, /VERDICT: FAIL/);
  assert.match(result.stdout, /checks\[0\]\.outputObserved/);
});
