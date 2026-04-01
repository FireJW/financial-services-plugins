import test from "node:test";
import assert from "node:assert/strict";
import {
  RUNTIME_COMPATIBILITY_PROBES,
  RUNTIME_COMPATIBILITY_SUITE_NAME,
  buildRuntimeCompatibilitySuitePreview,
  summarizeRuntimeCompatibilityProbeResults,
} from "../../scripts/runtime/runtime-compatibility-suite-lib.mjs";

test("runtime compatibility suite preview exposes the expected probe inventory", () => {
  const preview = buildRuntimeCompatibilitySuitePreview({
    requestedPluginDirs: ["C:\\plugins\\financial-analysis"],
    timeoutMs: 45_000,
    requireBuiltRuntime: true,
  });

  assert.equal(preview.suiteName, RUNTIME_COMPATIBILITY_SUITE_NAME);
  assert.equal(preview.probeCount, RUNTIME_COMPATIBILITY_PROBES.length);
  assert.equal(preview.probes.length, RUNTIME_COMPATIBILITY_PROBES.length);
  assert.deepEqual(preview.requestedPluginDirs, ["C:\\plugins\\financial-analysis"]);
  assert.equal(preview.requireBuiltRuntime, true);
  assert.equal(preview.invocation.timeoutMs, 45_000);
  assert.match(preview.invocation.displayCommand, /run-runtime-compatibility-suite\.mjs/);
  assert.ok(
    preview.probes.some((probe) =>
      /collect-runtime-surface-diff\.mjs$/i.test(probe.absoluteScriptPath),
    ),
    JSON.stringify(preview, null, 2),
  );
});

test("runtime compatibility suite summary distinguishes ok, skip, and fail states", () => {
  const okSummary = summarizeRuntimeCompatibilityProbeResults({
    probeResults: [{ ok: true }, { ok: true }, { ok: true }],
    vendorRuntimeBuilt: true,
    requireBuiltRuntime: false,
  });
  assert.equal(okSummary.status, "ok");
  assert.equal(okSummary.ok, true);
  assert.equal(okSummary.checkPassed, true);

  const skipSummary = summarizeRuntimeCompatibilityProbeResults({
    probeResults: [{ ok: false, skipped: true }, { ok: false, skipped: true }],
    vendorRuntimeBuilt: false,
    requireBuiltRuntime: false,
  });
  assert.equal(skipSummary.status, "skipped_vendor_unbuilt");
  assert.equal(skipSummary.ok, false);
  assert.equal(skipSummary.checkPassed, true);
  assert.equal(skipSummary.skippedProbeCount, 2);

  const failSummary = summarizeRuntimeCompatibilityProbeResults({
    probeResults: [{ ok: true }, { ok: false }, { ok: true }],
    vendorRuntimeBuilt: true,
    requireBuiltRuntime: false,
  });
  assert.equal(failSummary.status, "failed_runtime_probe");
  assert.equal(failSummary.ok, false);
  assert.equal(failSummary.checkPassed, false);
  assert.equal(failSummary.failedProbeCount, 1);

  const requiredBuildSummary = summarizeRuntimeCompatibilityProbeResults({
    probeResults: [{ ok: false, skipped: true }],
    vendorRuntimeBuilt: false,
    requireBuiltRuntime: true,
  });
  assert.equal(requiredBuildSummary.status, "skipped_vendor_unbuilt");
  assert.equal(requiredBuildSummary.checkPassed, false);
});
