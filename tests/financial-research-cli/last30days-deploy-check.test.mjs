import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("last30days-deploy-check emits stable contract envelope", () => {
  const result = runCli(
    [
      "last30days-deploy-check",
      "--input",
      "apps/financial-research-cli/examples/last30days-deploy-check-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "last30days-deploy-check": {
          status: "ready",
          workflow_kind: "last30days_deploy_check",
          skill_root: "apps/financial-research-cli/examples/fixtures/last30days-deploy-check/install",
          required_files: [
            { relative_path: "SKILL.md", exists: true },
            { relative_path: "README.md", exists: true },
            { relative_path: "scripts/last30days.py", exists: true },
          ],
          binary_status: {
            required_groups: [],
            optional: [{ command: "node", available: true }],
          },
          env_status: {
            env_file: { exists: true },
          },
          sqlite_candidates: ["apps/financial-research-cli/examples/fixtures/last30days-deploy-check/data/history.sqlite"],
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "last30days-deploy-check");
  assert.equal(payload.status, "ready");
  assert.equal(payload.workflow_kind, "last30days_deploy_check");
  assert.equal(payload.summary.deploy_status, "ready");
  assert.equal(payload.summary.missing_required_file_count, 0);
  assert.equal(payload.summary.env_file_present, true);
  assert.equal(payload.summary.sqlite_candidate_count, 1);
  assert.match(payload.execution_target.wrapper, /run_last30days_deploy_check\.cmd$/);
});

test("last30days-deploy-check dry-run shows wrapper execution plan", () => {
  const result = runCli([
    "last30days-deploy-check",
    "--input",
    "request.json",
    "--install-root",
    "D:/fixtures/last30days-skill",
    "--output",
    "out/last30days-deploy-check.json",
    "--markdown-output",
    "out/last30days-deploy-check.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--install-root",
    "D:/fixtures/last30days-skill",
    "--output",
    "out/last30days-deploy-check.json",
    "--markdown-output",
    "out/last30days-deploy-check.md",
  ]);
});
