import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.mjs";

test("loadConfig returns required fields", () => {
  const config = loadConfig();
  assert.equal(typeof config.vaultPath, "string");
  assert.equal(typeof config.vaultName, "string");
  assert.equal(typeof config.machineRoot, "string");
  assert.ok(Array.isArray(config.obsidian.cliCandidates));
  assert.ok(Array.isArray(config.obsidian.exeCandidates));
});

