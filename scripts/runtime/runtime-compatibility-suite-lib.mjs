import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { cliPath, repoRoot, runtimeRoot } from "./runtime-report-lib.mjs";

export const RUNTIME_COMPATIBILITY_SUITE_NAME = "runtime-compatibility";

export const RUNTIME_COMPATIBILITY_PROBES = Object.freeze([
  {
    id: "runtime-init-report",
    label: "Runtime init report",
    scriptPath: path.join("scripts", "runtime", "collect-runtime-init-report.mjs"),
  },
  {
    id: "runtime-plugin-compat-report",
    label: "Runtime plugin compatibility report",
    scriptPath: path.join("scripts", "runtime", "collect-runtime-compat-report.mjs"),
  },
  {
    id: "runtime-surface-diff",
    label: "Runtime surface diff",
    scriptPath: path.join("scripts", "runtime", "collect-runtime-surface-diff.mjs"),
  },
]);

export function isRecoveredRuntimeBuilt() {
  return existsSync(cliPath);
}

export function buildRuntimeCompatibilitySuitePreview(options = {}) {
  const requestedPluginDirs = [...(options.requestedPluginDirs ?? [])];
  const timeoutMs = Number.isFinite(options.timeoutMs) ? options.timeoutMs : null;
  const requireBuiltRuntime = Boolean(options.requireBuiltRuntime);
  const vendorRuntimeBuilt = isRecoveredRuntimeBuilt();

  return {
    suiteName: RUNTIME_COMPATIBILITY_SUITE_NAME,
    cwd: repoRoot,
    runtimeRoot,
    cliPath,
    vendorRuntimeBuilt,
    requestedPluginDirs,
    requireBuiltRuntime,
    probeCount: RUNTIME_COMPATIBILITY_PROBES.length,
    probes: RUNTIME_COMPATIBILITY_PROBES.map((probe) => ({
      ...probe,
      absoluteScriptPath: path.join(repoRoot, probe.scriptPath),
      command: buildProbeCommand(probe, requestedPluginDirs),
    })),
    invocation: {
      timeoutMs,
      displayCommand: buildSuiteDisplayCommand({
        requestedPluginDirs,
        timeoutMs,
        requireBuiltRuntime,
      }),
    },
  };
}

export function summarizeRuntimeCompatibilityProbeResults({
  probeResults = [],
  vendorRuntimeBuilt,
  requireBuiltRuntime = false,
}) {
  const successfulProbeCount = probeResults.filter((probe) => probe.ok).length;
  const failedProbeCount = probeResults.filter((probe) => !probe.ok).length;
  const skippedVendorUnbuilt = !vendorRuntimeBuilt;

  let status = "ok";
  if (skippedVendorUnbuilt) {
    status = "skipped_vendor_unbuilt";
  } else if (failedProbeCount > 0) {
    status = "failed_runtime_probe";
  }

  const ok = vendorRuntimeBuilt && failedProbeCount === 0;
  const checkPassed =
    status === "ok" || (status === "skipped_vendor_unbuilt" && !requireBuiltRuntime);

  return {
    probeCount: probeResults.length,
    successfulProbeCount,
    failedProbeCount,
    skippedProbeCount: skippedVendorUnbuilt ? probeResults.length : 0,
    status,
    ok,
    checkPassed,
  };
}

export function runRuntimeCompatibilitySuite(options = {}) {
  const requestedPluginDirs = [...(options.requestedPluginDirs ?? [])];
  const timeoutMs = Number.isFinite(options.timeoutMs) ? options.timeoutMs : 60_000;
  const requireBuiltRuntime = Boolean(options.requireBuiltRuntime);
  const vendorRuntimeBuilt = isRecoveredRuntimeBuilt();

  if (!vendorRuntimeBuilt) {
    const probes = RUNTIME_COMPATIBILITY_PROBES.map((probe) => ({
      id: probe.id,
      label: probe.label,
      scriptPath: probe.scriptPath,
      absoluteScriptPath: path.join(repoRoot, probe.scriptPath),
      ok: false,
      skipped: true,
      error: `Recovered runtime is not built yet. Expected: ${cliPath}`,
      command: buildProbeCommand(probe, requestedPluginDirs),
    }));
    const summary = summarizeRuntimeCompatibilityProbeResults({
      probeResults: probes,
      vendorRuntimeBuilt,
      requireBuiltRuntime,
    });

    return {
      generatedAt: new Date().toISOString(),
      suiteName: RUNTIME_COMPATIBILITY_SUITE_NAME,
      runtimeRoot,
      cliPath,
      requestedPluginDirs,
      requireBuiltRuntime,
      vendorRuntimeBuilt,
      skippedVendorUnbuilt: true,
      probes,
      summary,
    };
  }

  const probes = RUNTIME_COMPATIBILITY_PROBES.map((probe) =>
    runCompatibilityProbe(probe, { requestedPluginDirs, timeoutMs }),
  );
  const summary = summarizeRuntimeCompatibilityProbeResults({
    probeResults: probes,
    vendorRuntimeBuilt,
    requireBuiltRuntime,
  });

  return {
    generatedAt: new Date().toISOString(),
    suiteName: RUNTIME_COMPATIBILITY_SUITE_NAME,
    runtimeRoot,
    cliPath,
    requestedPluginDirs,
    requireBuiltRuntime,
    vendorRuntimeBuilt,
    skippedVendorUnbuilt: false,
    probes,
    summary,
  };
}

function runCompatibilityProbe(probe, options) {
  const command = buildProbeCommand(probe, options.requestedPluginDirs);
  const result = spawnSync(process.execPath, command.slice(1), {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: options.timeoutMs,
    maxBuffer: 16 * 1024 * 1024,
  });

  const base = {
    id: probe.id,
    label: probe.label,
    scriptPath: probe.scriptPath,
    absoluteScriptPath: path.join(repoRoot, probe.scriptPath),
    command,
    exitCode: result.status,
    signal: result.signal,
    stdout: result.stdout,
    stderr: result.stderr,
  };

  if (result.error) {
    return {
      ...base,
      ok: false,
      skipped: false,
      error: result.error.stack ?? result.error.message,
      payload: null,
    };
  }

  if (result.status !== 0) {
    return {
      ...base,
      ok: false,
      skipped: false,
      error: buildProbeFailureMessage(result),
      payload: safeParseJson(result.stdout),
    };
  }

  const payload = safeParseJson(result.stdout);
  if (payload == null) {
    return {
      ...base,
      ok: false,
      skipped: false,
      error: "Probe returned non-JSON stdout.",
      payload: null,
    };
  }

  const evaluation = evaluateProbePayload(probe.id, payload, options.requestedPluginDirs);

  return {
    ...base,
    ok: evaluation.ok,
    skipped: false,
    error: evaluation.error,
    payload,
  };
}

function buildProbeCommand(probe, requestedPluginDirs) {
  return [
    "node",
    path.join(repoRoot, probe.scriptPath),
    ...requestedPluginDirs,
  ];
}

function buildProbeFailureMessage(result) {
  return [
    `status=${result.status}`,
    result.signal ? `signal=${result.signal}` : null,
    result.stderr?.trim() ? `stderr=${result.stderr.trim()}` : null,
    result.stdout?.trim() ? `stdout=${result.stdout.trim()}` : null,
  ]
    .filter(Boolean)
    .join("\n");
}

function safeParseJson(stdout) {
  const text = stdout?.trim();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function buildSuiteDisplayCommand({ requestedPluginDirs, timeoutMs, requireBuiltRuntime }) {
  const parts = ["node", "scripts/runtime/run-runtime-compatibility-suite.mjs"];

  for (const pluginDir of requestedPluginDirs) {
    parts.push("--plugin-dir", pluginDir);
  }

  if (timeoutMs) {
    parts.push("--timeout-ms", String(timeoutMs));
  }

  if (requireBuiltRuntime) {
    parts.push("--require-built-runtime");
  }

  return parts.join(" ");
}

function evaluateProbePayload(probeId, payload, requestedPluginDirs) {
  if (probeId === "runtime-init-report") {
    const pluginCount = payload?.summary?.pluginCount ?? 0;
    const slashCommandCount = payload?.summary?.slashCommandCount ?? 0;

    if (pluginCount <= 0 || slashCommandCount <= 0) {
      return {
        ok: false,
        error: "Runtime init probe returned an empty plugin or slash-command surface.",
      };
    }

    return { ok: true, error: null };
  }

  if (probeId === "runtime-plugin-compat-report") {
    const discovered = payload?.summary?.discovered ?? 0;
    const loaded = payload?.summary?.loaded ?? 0;
    const loadedWithErrors = payload?.summary?.loadedWithErrors ?? 0;
    const expectedMinimum = requestedPluginDirs.length || 1;

    if (discovered < expectedMinimum) {
      return {
        ok: false,
        error: `Runtime plugin compatibility probe discovered ${discovered} plugins, expected at least ${expectedMinimum}.`,
      };
    }

    if (loaded !== discovered || loadedWithErrors > 0) {
      return {
        ok: false,
        error: "Runtime plugin compatibility probe reported unloaded plugins or plugin load errors.",
      };
    }

    return { ok: true, error: null };
  }

  if (probeId === "runtime-surface-diff") {
    const missingCount = payload?.summary?.missingCount ?? 0;
    const unexpectedCount = payload?.summary?.unexpectedCount ?? 0;

    if (missingCount > 0 || unexpectedCount > 0) {
      return {
        ok: false,
        error: `Runtime surface diff reported ${missingCount} missing and ${unexpectedCount} unexpected entries.`,
      };
    }

    return { ok: true, error: null };
  }

  return { ok: true, error: null };
}
