import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { validateCompactionSummary } from "../../scripts/runtime/orchestration-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");

test("compaction template accepts a valid summary", () => {
  const fixturePath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "compaction-summary-valid.md",
  );
  const report = validateCompactionSummary(readFileSync(fixturePath, "utf8"));

  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, "PASS");
});

test("compaction template rejects summaries that drop hard constraints", () => {
  const fixturePath = path.join(
    repoRoot,
    "tests",
    "fixtures",
    "runtime-orchestration",
    "compaction-summary-invalid.md",
  );
  const report = validateCompactionSummary(readFileSync(fixturePath, "utf8"));

  assert.equal(report.ok, false, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, "FAIL");
  assert.deepEqual(report.missingSections, ["Hard Constraints", "Non-goals"]);
});
