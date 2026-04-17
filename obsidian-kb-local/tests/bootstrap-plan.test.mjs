import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.mjs";
import { buildBootstrapPlan } from "../src/bootstrap-plan.mjs";

test("bootstrap plan stays within machine root", () => {
  const config = loadConfig();
  const plan = buildBootstrapPlan(config);

  for (const dir of plan.directories) {
    assert.ok(dir.startsWith(config.machineRoot), `Directory escaped root: ${dir}`);
  }

  for (const note of plan.notes) {
    assert.ok(note.path.startsWith(config.machineRoot), `Note escaped root: ${note.path}`);
    assert.equal(typeof note.content, "string");
    assert.ok(note.content.length > 0);
  }
});

