import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { makeRunner, parseStdoutJson } from "./helpers.mjs";

test("wechat-push-readiness emits stable contract envelope", () => {
  const result = runCli(
    [
      "wechat-push-readiness",
      "--input",
      "apps/financial-research-cli/examples/wechat-push-readiness-article-publish-request.json",
      "--json",
    ],
    {
      runner: makeRunner({
        "wechat-push-readiness": {
          status: "ok",
          workflow_kind: "wechat_push_readiness_audit",
          readiness_level: "ready",
          ready_for_real_push: true,
          push_readiness: { status: "ready_for_api_push" },
          credential_check: { status: "ready", source: "env_file" },
          live_auth_check: { status: "not_run" },
          workflow_publication_gate: { publication_readiness: "ready" },
          completion_check: { status: "ready" },
          operator_summary: { operator_status: "ready" },
        },
      }),
    },
  );

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.cli_command, "wechat-push-readiness");
  assert.equal(payload.summary.readiness_level, "ready");
  assert.equal(payload.summary.ready_for_real_push, true);
  assert.equal(payload.summary.credential_status, "ready");
  assert.match(payload.execution_target.wrapper, /run_wechat_push_readiness\.cmd$/);
});

test("wechat-push-readiness dry-run forwards audit options", () => {
  const result = runCli([
    "wechat-push-readiness",
    "--input",
    "request.json",
    "--cover-image-url",
    "https://example.com/cover.png",
    "--human-review-approved",
    "--human-review-approved-by",
    "OfflineSmoke",
    "--wechat-env-file",
    "apps/financial-research-cli/examples/fixtures/wechat-offline.env",
    "--validate-live-auth",
    "--timeout-seconds",
    "12",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.execution_plan.args, [
    "request.json",
    "--cover-image-url",
    "https://example.com/cover.png",
    "--human-review-approved",
    "--human-review-approved-by",
    "OfflineSmoke",
    "--wechat-env-file",
    "apps/financial-research-cli/examples/fixtures/wechat-offline.env",
    "--validate-live-auth",
    "--timeout-seconds",
    "12",
  ]);
});

test("wechat-push-readiness requires an input path", () => {
  const result = runCli(["wechat-push-readiness"]);
  assert.equal(result.exitCode, 1);
  assert.match(result.stderr, /Missing required --input <path> for wechat-push-readiness/);
});
