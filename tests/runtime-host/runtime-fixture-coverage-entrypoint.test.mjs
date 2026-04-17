import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  RUNTIME_CLASSIC_CASES,
  RUNTIME_REAL_TASK_FIXTURE_MANIFEST,
  buildRuntimeFixtureCoverageReport,
} from "../../scripts/runtime/runtime-host-reliability-suite-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const scriptPath = path.join(
  repoRoot,
  "scripts",
  "runtime",
  "report-runtime-fixture-coverage.mjs",
);

test("runtime fixture coverage report shows all classic cases are covered", () => {
  const report = buildRuntimeFixtureCoverageReport();

  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.fixtureCount, RUNTIME_REAL_TASK_FIXTURE_MANIFEST.length);
  assert.equal(report.classicCaseCount, RUNTIME_CLASSIC_CASES.length);
  assert.equal(report.coveredClassicCaseCount, RUNTIME_CLASSIC_CASES.length);
  assert.equal(report.missingClassicCases.length, 0, JSON.stringify(report, null, 2));
  assert.equal(report.missingFixtureRoots.length, 0, JSON.stringify(report, null, 2));
});

test("runtime fixture coverage entrypoint supports json output and check mode", () => {
  const result = spawnSync(
    "node",
    [scriptPath, "--json", "--check"],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.ok, true, result.stdout);
  assert.equal(payload.coveredClassicCaseCount, payload.classicCaseCount, result.stdout);
  assert.ok(
    payload.fixtures.some((fixture) => fixture.id === "workflow-improvement-loop"),
    result.stdout,
  );
});
