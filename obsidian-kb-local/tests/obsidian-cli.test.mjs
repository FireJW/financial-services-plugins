import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.mjs";
import { buildObsidianArgs } from "../src/obsidian-cli.mjs";

test("vault selector is prepended first", () => {
  const config = loadConfig();
  const args = buildObsidianArgs(config, ["read", "path=README.md"]);

  assert.equal(args[0], `vault=${config.vaultName}`);
  assert.equal(args[1], "read");
});

