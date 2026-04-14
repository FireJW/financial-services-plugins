import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("agent-reach-deploy-check emits stable contract envelope", () => {
  const result = runCli(
    [
      "agent-reach-deploy-check",
      "--input",
      "apps/financial-research-cli/examples/agent-reach-deploy-check-smoke-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "agent-reach-deploy-check": {
          status: "ready",
          workflow_kind: "agent_reach_deploy_check",
          install_root: "apps/financial-research-cli/examples/fixtures/agent-reach-deploy-check/install",
          pseudo_home: "apps/financial-research-cli/examples/fixtures/agent-reach-deploy-check/pseudo-home",
          python_status: { status: "ok" },
          binaries: {
            "agent-reach": "ok",
            gh: "ok",
            "yt-dlp": "ok",
            node: "ok",
            npm: "ok",
          },
          channels: {
            web_jina: "ok",
            github: "ok",
            rss: "ok",
          },
          channels_failed: [],
          credential_gaps: [],
          core_channels_ready: true,
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "agent-reach-deploy-check");
  assert.equal(payload.workflow_kind, "agent_reach_deploy_check");
  assert.equal(payload.summary.deploy_status, "ready");
  assert.equal(payload.summary.core_channels_ready, true);
  assert.equal(payload.summary.channel_ok_count, 3);
  assert.equal(payload.summary.missing_binary_count, 0);
  assert.match(payload.execution_target.wrapper, /run_agent_reach_deploy_check\.cmd$/);
});

test("agent-reach-deploy-check dry-run forwards deploy overrides", () => {
  const result = runCli([
    "agent-reach-deploy-check",
    "--input",
    "request.json",
    "--install-root",
    "D:/fixtures/agent-reach",
    "--pseudo-home",
    "D:/fixtures/agent-reach-home",
    "--python-binary",
    "D:/fixtures/python.exe",
    "--output",
    "out/agent-reach-deploy-check.json",
    "--markdown-output",
    "out/agent-reach-deploy-check.md",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--install-root",
    "D:/fixtures/agent-reach",
    "--pseudo-home",
    "D:/fixtures/agent-reach-home",
    "--python-binary",
    "D:/fixtures/python.exe",
    "--output",
    "out/agent-reach-deploy-check.json",
    "--markdown-output",
    "out/agent-reach-deploy-check.md",
  ]);
});
