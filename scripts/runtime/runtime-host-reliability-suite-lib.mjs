import path from "node:path";
import process from "node:process";
import { repoRoot } from "./runtime-report-lib.mjs";

export const RUNTIME_HOST_RELIABILITY_SUITE_NAME = "runtime-host-reliability";

export const RUNTIME_HOST_RELIABILITY_TESTS = Object.freeze([
  path.join("tests", "runtime-host", "runtime-real-task-fixtures.test.mjs"),
  path.join("tests", "runtime-host", "runtime-prompt-budget.test.mjs"),
  path.join("tests", "runtime-host", "runtime-attempt-ledger.test.mjs"),
  path.join("tests", "runtime-host", "worker-verifier-entrypoints.test.mjs"),
  path.join("tests", "runtime-host", "structured-verifier-contract.test.mjs"),
  path.join("tests", "runtime-host", "structured-verifier-entrypoints.test.mjs"),
  path.join("tests", "runtime-host", "verification-pass.test.mjs"),
  path.join("tests", "runtime-host", "intent-preservation.test.mjs"),
  path.join("tests", "runtime-host", "session-memory-state.test.mjs"),
  path.join("tests", "runtime-host", "runtime-host-reliability-suite-entrypoint.test.mjs"),
]);

export function buildRuntimeHostReliabilitySuitePreview(options = {}) {
  const forwardedArgs = [...(options.forwardedArgs ?? [])];
  const command = options.command ?? process.execPath;
  const args = ["--test", ...forwardedArgs, ...RUNTIME_HOST_RELIABILITY_TESTS];

  return {
    suiteName: RUNTIME_HOST_RELIABILITY_SUITE_NAME,
    cwd: repoRoot,
    testCount: RUNTIME_HOST_RELIABILITY_TESTS.length,
    testFiles: [...RUNTIME_HOST_RELIABILITY_TESTS],
    invocation: {
      command,
      args,
      forwardedArgs,
      displayCommand: ["node", "--test", ...forwardedArgs, ...RUNTIME_HOST_RELIABILITY_TESTS].join(
        " ",
      ),
    },
  };
}
