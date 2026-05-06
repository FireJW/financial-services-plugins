import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { repoRoot } from "../../apps/financial-research-cli/src/config/defaults.mjs";
import { runWorkflowCommand } from "../../apps/financial-research-cli/src/runtime/headlessSession.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("multiplatform-repurpose emits stable contract envelope", () => {
  const result = runCli(
    [
      "multiplatform-repurpose",
      "--input",
      "financial-analysis/skills/autoresearch-info-index/tests/fixtures/multiplatform-repurpose/request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "multiplatform-repurpose": {
          status: "ok",
          workflow_kind: "multiplatform_repurpose",
          run_id: "sample-agent-budget-discipline",
          source_integrity: { status: "ok", core_thesis: "Agent budget discipline thesis" },
          platforms: {
            wechat_article: { source_integrity_status: "ok" },
            xiaohongshu_cards: { source_integrity_status: "ok" },
          },
          manifest_path: "out/manifest.json",
          report_path: "out/report.md",
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "multiplatform-repurpose");
  assert.equal(payload.workflow_kind, "multiplatform_repurpose");
  assert.equal(payload.summary.run_id, "sample-agent-budget-discipline");
  assert.equal(payload.summary.source_integrity_status, "ok");
  assert.equal(payload.summary.platform_count, 2);
  assert.match(payload.execution_target.wrapper, /run_multiplatform_repurpose\.cmd$/);
});

test("multiplatform-repurpose dry-run forwards output dir", () => {
  const result = runCli([
    "multiplatform-repurpose",
    "--input",
    "request.json",
    "--output-dir",
    "out/multiplatform",
    "--output",
    "out/manifest-copy.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--output-dir",
    "out/multiplatform",
    "--output",
    "out/manifest-copy.json",
  ]);
});

test("multiplatform-repurpose requires an input path", () => {
  const result = runCli(["multiplatform-repurpose"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for multiplatform-repurpose/);
});

test("multiplatform-repurpose runner keeps repo-relative input paths valid", () => {
  let seen = null;
  const command = {
    name: "multiplatform-repurpose",
    script: "multiplatform_repurpose.py",
    wrapper: "run_multiplatform_repurpose.cmd",
    buildArgs() {
      return ["financial-analysis/skills/autoresearch-info-index/tests/fixtures/multiplatform-repurpose/request.json"];
    },
  };

  const result = runWorkflowCommand("multiplatform-repurpose", command, {}, {
    spawnSyncImpl(wrapper, args, options) {
      seen = { wrapper, args, options };
      return {
        status: 0,
        stdout: JSON.stringify({ status: "ok", workflow_kind: "multiplatform_repurpose" }),
        stderr: "",
      };
    },
  });

  assert.equal(result.ok, true);
  assert.equal(seen.options.cwd, repoRoot);
  assert.equal(seen.options.shell, undefined);
  assert.match(seen.wrapper, /python\.exe$|py\.exe$/i);
  assert.match(seen.args.at(-2), /multiplatform_repurpose\.py$/);
  assert.deepEqual(seen.args.slice(-1), [
    "financial-analysis/skills/autoresearch-info-index/tests/fixtures/multiplatform-repurpose/request.json",
  ]);
});

test("multiplatform-repurpose runner rejects empty wrapper stdout", () => {
  const command = {
    name: "multiplatform-repurpose",
    script: "multiplatform_repurpose.py",
    wrapper: "run_multiplatform_repurpose.cmd",
    buildArgs() {
      return ["request.json"];
    },
  };

  const result = runWorkflowCommand("multiplatform-repurpose", command, {}, {
    spawnSyncImpl() {
      return { status: 0, stdout: "", stderr: "" };
    },
  });

  assert.equal(result.ok, false);
  assert.match(result.error, /produced no JSON stdout/);
});

test("multiplatform-repurpose runner reports spawn errors instead of using a local fallback", () => {
  const command = {
    name: "multiplatform-repurpose",
    script: "multiplatform_repurpose.py",
    wrapper: "run_multiplatform_repurpose.cmd",
    buildArgs() {
      return ["request.json"];
    },
    fallbackExecuteLocal() {
      return { status: "ok", runtime_fallback: "node_no_spawn" };
    },
  };

  const result = runWorkflowCommand("multiplatform-repurpose", command, {}, {
    spawnSyncImpl() {
      return { error: new Error("spawn blocked") };
    },
  });

  assert.equal(result.ok, false);
  assert.match(result.error, /spawn blocked/);
});
