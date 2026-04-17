import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  RUNTIME_HOST_RELIABILITY_TESTS,
  buildRuntimeHostReliabilitySuitePreview,
} from "../../scripts/runtime/runtime-host-reliability-suite-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const suiteScript = path.join(
  repoRoot,
  "scripts",
  "runtime",
  "run-runtime-host-reliability-suite.mjs",
);

test("runtime host reliability suite preview includes the expected regression files", () => {
  const preview = buildRuntimeHostReliabilitySuitePreview({
    forwardedArgs: ["--test-name-pattern", "multilingual"],
  });

  assert.equal(preview.suiteName, "runtime-host-reliability");
  assert.equal(preview.testCount, RUNTIME_HOST_RELIABILITY_TESTS.length);
  assert.ok(preview.realTaskFixtureCount >= 6, JSON.stringify(preview, null, 2));
  assert.equal(preview.coveredClassicCaseCount, preview.classicCaseCount);
  assert.ok(
    preview.testFiles.includes(
      path.join("tests", "runtime-host", "intent-preservation.test.mjs"),
    ),
  );
  assert.ok(
    preview.testFiles.includes(
      path.join("tests", "runtime-host", "runtime-real-task-fixtures.test.mjs"),
    ),
  );
  assert.deepEqual(preview.invocation.forwardedArgs, ["--test-name-pattern", "multilingual"]);
  assert.ok(preview.invocation.args.includes("--test-name-pattern"));
});

test("runtime host reliability suite entrypoint supports dry-run json output", () => {
  const result = spawnSync(
    "node",
    [
      suiteScript,
      "--dry-run",
      "--json",
      "--",
      "--test-name-pattern",
      "multilingual",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.suiteName, "runtime-host-reliability");
  assert.equal(payload.testCount, RUNTIME_HOST_RELIABILITY_TESTS.length);
  assert.ok(payload.realTaskFixtureCount >= 6, result.stdout);
  assert.equal(payload.coveredClassicCaseCount, payload.classicCaseCount);
  assert.match(payload.invocation.displayCommand, /node --test/);
  assert.ok(payload.invocation.args.includes("--test-name-pattern"), result.stdout);
  assert.ok(
    payload.testFiles.includes("tests\\runtime-host\\session-memory-state.test.mjs") ||
      payload.testFiles.includes("tests/runtime-host/session-memory-state.test.mjs"),
    result.stdout,
  );
});
