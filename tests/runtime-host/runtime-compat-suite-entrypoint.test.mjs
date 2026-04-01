import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  RUNTIME_COMPAT_PROBES,
  buildRuntimeCompatSuitePreview,
  getRuntimeCompatSuiteExitCode,
} from "../../scripts/runtime/runtime-compat-suite-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const suiteScript = path.join(repoRoot, "scripts", "runtime", "run-runtime-compat-suite.mjs");
const financialAnalysisPluginDir = path.join(repoRoot, "financial-analysis");

test("runtime compat alias preview reuses the canonical compatibility suite", () => {
  const preview = buildRuntimeCompatSuitePreview({
    pluginDirs: [financialAnalysisPluginDir],
    requireBuiltRuntime: true,
  });

  assert.equal(preview.suiteName, "runtime-compatibility");
  assert.equal(preview.probeCount, RUNTIME_COMPAT_PROBES.length);
  assert.deepEqual(preview.requestedPluginDirs, [financialAnalysisPluginDir]);
  assert.equal(preview.requireBuiltRuntime, true);
  assert.deepEqual(
    preview.probes.map((probe) => probe.id),
    RUNTIME_COMPAT_PROBES.map((probe) => probe.id),
  );
});

test("runtime compat alias exit code follows canonical checkPassed semantics", () => {
  assert.equal(
    getRuntimeCompatSuiteExitCode({
      summary: {
        checkPassed: true,
      },
    }),
    0,
  );

  assert.equal(
    getRuntimeCompatSuiteExitCode({
      summary: {
        checkPassed: false,
      },
    }),
    1,
  );
});

test("runtime compat alias entrypoint supports dry-run json output", () => {
  const result = spawnSync(
    "node",
    [
      suiteScript,
      "--dry-run",
      "--json",
      "--plugin-dir",
      financialAnalysisPluginDir,
      "--require-built-runtime",
    ],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.suiteName, "runtime-compatibility");
  assert.equal(payload.probeCount, RUNTIME_COMPAT_PROBES.length);
  assert.deepEqual(payload.requestedPluginDirs, [financialAnalysisPluginDir]);
  assert.equal(payload.requireBuiltRuntime, true);
  assert.ok(payload.probes.every((probe) => probe.command[0] === "node"), result.stdout);
});

test("runtime compat alias entrypoint executes with canonical report schema", () => {
  const result = spawnSync("node", [suiteScript, "--json", "--timeout-ms", "10000"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 60_000,
    maxBuffer: 16 * 1024 * 1024,
  });

  assert.notEqual(result.status, null, result.stderr || "runtime compat alias timed out");
  const payload = JSON.parse(result.stdout);
  const expectedExitCode = payload.summary.checkPassed ? 0 : 1;

  assert.equal(result.status, expectedExitCode, result.stderr || result.stdout);
  assert.equal(payload.suiteName, "runtime-compatibility");
  assert.equal(payload.probes.length, RUNTIME_COMPAT_PROBES.length);
  assert.equal(payload.vendorRuntimeBuilt, true, result.stdout);
  assert.ok(
    payload.summary.status === "ok" || payload.summary.status === "failed_runtime_probe",
    result.stdout,
  );
  if (payload.summary.status === "ok") {
    assert.equal(payload.summary.checkPassed, true, result.stdout);
    assert.ok(payload.probes.every((probe) => probe.ok === true), result.stdout);
    return;
  }

  assert.equal(payload.summary.checkPassed, false, result.stdout);
  assert.ok(payload.probes.some((probe) => probe.ok === false), result.stdout);
});
