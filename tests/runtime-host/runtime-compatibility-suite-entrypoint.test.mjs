import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  RUNTIME_COMPATIBILITY_PROBES,
  RUNTIME_COMPATIBILITY_SUITE_NAME,
} from "../../scripts/runtime/runtime-compatibility-suite-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const suiteScript = path.join(
  repoRoot,
  "scripts",
  "runtime",
  "run-runtime-compatibility-suite.mjs",
);
const cliPath = path.join(repoRoot, "vendor", "claude-code-recovered", "dist", "cli.js");

test("runtime compatibility suite entrypoint supports dry-run json output", () => {
  const result = spawnSync("node", [suiteScript, "--dry-run", "--json"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.suiteName, RUNTIME_COMPATIBILITY_SUITE_NAME);
  assert.equal(payload.probeCount, RUNTIME_COMPATIBILITY_PROBES.length);
  assert.equal(payload.probes.length, RUNTIME_COMPATIBILITY_PROBES.length);
  assert.match(payload.invocation.displayCommand, /run-runtime-compatibility-suite\.mjs/);
});

test("runtime compatibility suite reports skip semantics when the recovered runtime is not built", (t) => {
  if (existsSync(cliPath)) {
    t.skip("Recovered runtime is built locally; skip missing-build semantics test.");
    return;
  }

  const result = spawnSync("node", [suiteScript, "--json", "--check"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20_000,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.vendorRuntimeBuilt, false);
  assert.equal(payload.skippedVendorUnbuilt, true);
  assert.equal(payload.summary.status, "skipped_vendor_unbuilt");
  assert.equal(payload.summary.checkPassed, true);
  assert.equal(payload.probes.length, RUNTIME_COMPATIBILITY_PROBES.length);
});

test("runtime compatibility suite can require a built recovered runtime", (t) => {
  if (existsSync(cliPath)) {
    t.skip("Recovered runtime is built locally; skip explicit missing-build failure test.");
    return;
  }

  const result = spawnSync(
    "node",
    [suiteScript, "--json", "--check", "--require-built-runtime"],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 20_000,
    },
  );

  assert.equal(result.status, 1, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.vendorRuntimeBuilt, false);
  assert.equal(payload.summary.status, "skipped_vendor_unbuilt");
  assert.equal(payload.summary.checkPassed, false);
});

test("runtime compatibility suite executes the probe set when the recovered runtime is built", (t) => {
  if (!existsSync(cliPath)) {
    t.skip("Recovered runtime is not built locally; skip probe execution test.");
    return;
  }

  const result = spawnSync("node", [suiteScript, "--json", "--timeout-ms", "10000"], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 60_000,
    maxBuffer: 16 * 1024 * 1024,
  });

  assert.notEqual(result.status, null, result.stderr || "runtime compatibility suite timed out");
  const payload = JSON.parse(result.stdout);
  const expectedExitCode = payload.summary.checkPassed ? 0 : 1;

  assert.equal(result.status, expectedExitCode, result.stderr || result.stdout);
  assert.equal(payload.vendorRuntimeBuilt, true, result.stdout);
  assert.equal(payload.skippedVendorUnbuilt, false, result.stdout);
  assert.equal(payload.probes.length, RUNTIME_COMPATIBILITY_PROBES.length, result.stdout);
  assert.ok(
    payload.summary.status === "ok" || payload.summary.status === "failed_runtime_probe",
    result.stdout,
  );

  if (payload.summary.status === "ok") {
    assert.equal(payload.summary.checkPassed, true, result.stdout);
    assert.ok(payload.probes.every((probe) => probe.ok), result.stdout);
    return;
  }

  assert.equal(payload.summary.checkPassed, false, result.stdout);
  assert.ok(payload.probes.some((probe) => !probe.ok), result.stdout);
  assert.ok(
    payload.probes.some((probe) => typeof probe.error === "string" && probe.error.length > 0),
    result.stdout,
  );
});
