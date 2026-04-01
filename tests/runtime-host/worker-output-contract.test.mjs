import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { validateWorkerOutput } from "../../scripts/runtime/orchestration-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");

test("worker output contract accepts the valid fixture", () => {
  const fixturePath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "worker-output-valid.md",
  );
  const report = validateWorkerOutput(readFileSync(fixturePath, "utf8"));

  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, "PASS");
  assert.deepEqual(report.missingSections, []);
});

test("worker output contract rejects missing required sections", () => {
  const fixturePath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "worker-output-invalid.md",
  );
  const report = validateWorkerOutput(readFileSync(fixturePath, "utf8"));

  assert.equal(report.ok, false, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, "FAIL");
  assert.deepEqual(report.missingSections, ["Risks"]);
});
