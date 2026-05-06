import assert from "node:assert/strict";

export function parseStdoutJson(result) {
  assert.equal(result.stderr, "", result.stderr);
  return JSON.parse(result.stdout);
}

export function makeRunner(payloadByCommand) {
  return (commandName) => {
    const payload = payloadByCommand[commandName];
    if (!payload) {
      return { ok: false, error: `No mocked payload for ${commandName}` };
    }
    return { ok: true, payload };
  };
}
