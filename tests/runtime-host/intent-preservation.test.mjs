import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { validateCompactionSummary } from "../../scripts/runtime/orchestration-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const scriptPath = path.join(repoRoot, "scripts", "runtime", "preserve-user-intent.mjs");

test("intent preservation script carries user intent and hard constraints into the compact summary", () => {
  const intentPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-state",
    "sample-user-intent.md",
  );
  const result = spawnSync(
    "node",
    [
      scriptPath,
      "--intent-file",
      intentPath,
      "--current-state",
      "- Contracts are drafted.",
      "--next-step",
      "- Implement the verification wrapper.",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /Build the P0\/P1 runtime hardening layer first\./);
  assert.match(result.stdout, /File safety and disk safety are the highest priority\./);
  assert.match(result.stdout, /Do not implement the full Dream Memory pipeline\./);

  const report = validateCompactionSummary(result.stdout);
  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
});

test("intent preservation script can derive a compact summary from a raw user request", () => {
  const intentPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-state",
    "sample-user-request.txt",
  );
  const result = spawnSync(
    "node",
    [
      scriptPath,
      "--input",
      intentPath,
      "--current-state",
      "Contracts are drafted.",
      "--next-step",
      "Implement the verification wrapper.",
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

  assert.equal(payload.intentValidation.ok, true, result.stdout);
  assert.equal(payload.compactValidation.ok, true, result.stdout);
  assert.match(payload.intentMarkdown, /Highest priority is file safety and disk safety/i);
  assert.match(payload.compactSummary, /Do not implement the full Dream Memory pipeline/i);
});

test("intent preservation script can emit structured intent markdown", () => {
  const intentPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-state",
    "sample-user-request.txt",
  );
  const result = spawnSync(
    "node",
    [
      scriptPath,
      "--input",
      intentPath,
      "--output-kind",
      "intent",
      "--format",
      "text",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /## User Intent/);
  assert.match(result.stdout, /## Hard Constraints/);
  assert.match(result.stdout, /## Non-goals/);
});

test("intent preservation script keeps Chinese hard constraints and non-goals separated", () => {
  const inputPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-state",
    "sample-user-request-multilingual.txt",
  );
  const result = spawnSync(
    "node",
    [
      scriptPath,
      "--input",
      inputPath,
      "--output-kind",
      "intent",
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

  assert.equal(payload.intentValidation.ok, true, result.stdout);
  assert.match(payload.intentMarkdown, /最高优先级是文件安全和磁盘安全。/);
  assert.match(payload.intentMarkdown, /不要破坏当前 headless 回归测试。/);
  assert.match(payload.intentMarkdown, /不要在这一步实现完整 Dream Memory pipeline。/);
  assert.match(payload.intentMarkdown, /先别产品化 financial CLI。/);
});

test("intent preservation script preserves structured multilingual intent into compaction", () => {
  const inputPath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-state",
    "sample-user-intent-multilingual.md",
  );
  const result = spawnSync(
    "node",
    [
      scriptPath,
      "--intent-file",
      inputPath,
      "--current-state",
      "Worker/verifier wrapper 已经可用。",
      "--next-step",
      "补齐中文和 mixed-language 回归。",
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

  assert.equal(payload.intentValidation.ok, true, result.stdout);
  assert.equal(payload.compactValidation.ok, true, result.stdout);
  assert.match(payload.compactSummary, /最高优先级是文件安全和磁盘安全。/);
  assert.match(payload.compactSummary, /不要在这一步实现完整 Dream Memory pipeline。/);
  assert.match(payload.compactSummary, /补齐中文和 mixed-language 回归。/);
});
