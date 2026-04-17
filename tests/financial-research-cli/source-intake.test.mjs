import test from "node:test";
import assert from "node:assert/strict";

import { runCli } from "../../apps/financial-research-cli/src/cli.mjs";
import { parseStdoutJson } from "./helpers.mjs";

test("source-intake dry-run routes reddit surface to reddit-bridge", () => {
  const result = runCli([
    "source-intake",
    "--surface",
    "reddit",
    "--input",
    "apps/financial-research-cli/examples/reddit-bridge-smoke-request.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.dry_run, true);
  assert.equal(payload.execution_plan.cli_command, "source-intake");
  assert.equal(payload.execution_plan.delegated_command, "reddit-bridge");
  assert.equal(payload.execution_plan.routed_via, "source-intake");
  assert.match(payload.execution_plan.wrapper, /run_reddit_bridge\.cmd$/);
});

test("source-intake dry-run routes last30days surface to last30days-bridge", () => {
  const result = runCli([
    "source-intake",
    "--surface",
    "last30days",
    "--input",
    "apps/financial-research-cli/examples/last30days-bridge-smoke-request.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.execution_plan.delegated_command, "last30days-bridge");
  assert.match(payload.execution_plan.wrapper, /run_last30days_bridge\.cmd$/);
});

test("source-intake dry-run routes opencli aliases to opencli-index", () => {
  const result = runCli([
    "source-intake",
    "--surface",
    "opencli-index",
    "--input",
    "apps/financial-research-cli/examples/opencli-index-smoke-request.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.execution_plan.delegated_command, "opencli-index");
  assert.match(payload.execution_plan.wrapper, /run_opencli_bridge\.cmd$/);
});

test("source-intake dry-run routes agent-reach aliases to agent-reach-bridge", () => {
  const result = runCli([
    "source-intake",
    "--surface",
    "agent-reach",
    "--file",
    "agent-reach.json",
    "--topic",
    "AI agent frontier",
    "--channel",
    "github",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.execution_plan.delegated_command, "agent-reach-bridge");
  assert.deepEqual(payload.execution_plan.args, [
    "--file",
    "agent-reach.json",
    "--topic",
    "AI agent frontier",
    "--channels",
    "github",
  ]);
});

test("source-intake dry-run routes x aliases to x-index", () => {
  const result = runCli([
    "source-intake",
    "--surface",
    "x",
    "--input",
    "apps/financial-research-cli/examples/x-index-smoke-request.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.execution_plan.delegated_command, "x-index");
  assert.match(payload.execution_plan.wrapper, /run_x_index\.cmd$/);
});

test("source-intake dry-run routes fieldtheory aliases to fieldtheory-index", () => {
  const result = runCli([
    "source-intake",
    "--surface",
    "fieldtheory",
    "--input",
    "apps/financial-research-cli/examples/fieldtheory-index-smoke-request.json",
    "--dry-run",
    "--json",
  ]);

  assert.equal(result.exitCode, 0, result.stderr);
  const payload = parseStdoutJson(result);
  assert.equal(payload.execution_plan.delegated_command, "fieldtheory-index");
  assert.match(payload.execution_plan.wrapper, /run_fieldtheory_bookmark_index\.cmd$/);
});

test("source-intake requires a known surface", () => {
  const missing = runCli(["source-intake", "--input", "request.json"]);
  assert.equal(missing.exitCode, 1);
  assert.match(missing.stderr, /source-intake requires --surface <x\|reddit\|last30days\|opencli\|agent-reach\|fieldtheory>/);

  const unknown = runCli(["source-intake", "--surface", "rss", "--input", "request.json"]);
  assert.equal(unknown.exitCode, 1);
  assert.match(unknown.stderr, /source-intake requires --surface <x\|reddit\|last30days\|opencli\|agent-reach\|fieldtheory>/);
});
