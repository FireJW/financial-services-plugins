import {
  RUNTIME_COMPATIBILITY_PROBES,
  RUNTIME_COMPATIBILITY_SUITE_NAME,
  buildRuntimeCompatibilitySuitePreview,
  runRuntimeCompatibilitySuite,
} from "./runtime-compatibility-suite-lib.mjs";

export const RUNTIME_COMPAT_SUITE_NAME = RUNTIME_COMPATIBILITY_SUITE_NAME;
export const RUNTIME_COMPAT_PROBES = RUNTIME_COMPATIBILITY_PROBES;

export function buildRuntimeCompatSuitePreview(options = {}) {
  return buildRuntimeCompatibilitySuitePreview({
    requestedPluginDirs: options.pluginDirs ?? [],
    timeoutMs: options.timeoutMs,
    requireBuiltRuntime: options.requireBuiltRuntime,
  });
}

export function runRuntimeCompatSuite(options = {}) {
  return runRuntimeCompatibilitySuite({
    requestedPluginDirs: options.pluginDirs ?? [],
    timeoutMs: options.timeoutMs,
    requireBuiltRuntime: options.requireBuiltRuntime,
  });
}

export function getRuntimeCompatSuiteExitCode(report) {
  return report?.summary?.checkPassed ? 0 : 1;
}

export function renderRuntimeCompatSuitePreview(preview) {
  const lines = [];
  lines.push(`Suite: ${preview.suiteName}`);
  lines.push(`Cwd: ${preview.cwd}`);
  lines.push(`Runtime built: ${preview.vendorRuntimeBuilt}`);
  lines.push(`Probes: ${preview.probeCount}`);
  lines.push(`Command: ${preview.invocation.displayCommand}`);
  lines.push("Probe scripts:");
  for (const probe of preview.probes) {
    lines.push(`- ${probe.scriptPath}`);
  }

  return `${lines.join("\n")}\n`;
}

export function renderRuntimeCompatSuiteReport(report) {
  const lines = [];
  lines.push(`Suite: ${report.suiteName}`);
  lines.push(`Runtime built: ${report.vendorRuntimeBuilt}`);
  lines.push(`Status: ${report.summary.status}`);
  lines.push(`Check passed: ${report.summary.checkPassed}`);
  lines.push(`Successful probes: ${report.summary.successfulProbeCount}/${report.summary.probeCount}`);

  if (report.skippedVendorUnbuilt) {
    lines.push(`Skip reason: Recovered runtime is not built. Expected ${report.cliPath}`);
  }

  lines.push("Probes:");
  for (const probe of report.probes) {
    const state = probe.skipped ? "SKIPPED" : probe.ok ? "OK" : "FAIL";
    lines.push(`- ${probe.label}: ${state}`);
    if (probe.error) {
      lines.push(`  ${probe.error.split(/\r?\n/)[0]}`);
    }
  }

  return `${lines.join("\n")}\n`;
}
