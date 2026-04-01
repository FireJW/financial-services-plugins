import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  STRUCTURED_VERIFIER_SCHEMA_VERSION,
  buildRetryPrompt,
  renderStructuredVerifierMarkdown,
  validateStructuredVerifierReport,
} from "../../scripts/runtime/orchestration-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");

function fixturePath(name) {
  return path.join(repoRoot, "tests", "fixtures", "runtime-orchestration", name);
}

test("structured verifier validator accepts the valid fixture", () => {
  const report = validateStructuredVerifierReport(
    readFileSync(fixturePath("structured-verifier-valid.json"), "utf8"),
  );

  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.schemaVersion, STRUCTURED_VERIFIER_SCHEMA_VERSION);
  assert.equal(report.verdict, "PASS");
  assert.equal(report.hasAdversarialProbe, true);
  assert.equal(report.checks.length, 2);
});

test("structured verifier validator rejects a missing verdict", () => {
  const report = validateStructuredVerifierReport(
    readFileSync(fixturePath("structured-verifier-invalid-missing-verdict.json"), "utf8"),
  );

  assert.equal(report.ok, false, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, null);
  assert.ok(report.invalidFields.includes("verdict"), JSON.stringify(report, null, 2));
});

test("structured verifier validator rejects a missing check field", () => {
  const report = validateStructuredVerifierReport(
    readFileSync(
      fixturePath("structured-verifier-invalid-missing-check-field.json"),
      "utf8",
    ),
  );

  assert.equal(report.ok, false, JSON.stringify(report, null, 2));
  assert.ok(
    report.invalidFields.includes("checks[0].outputObserved"),
    JSON.stringify(report, null, 2),
  );
});

test("structured verifier validator accepts fenced json input", () => {
  const validFixture = readFileSync(fixturePath("structured-verifier-valid.json"), "utf8");
  const fencedJson = ["```json", validFixture.trim(), "```"].join("\n");
  const report = validateStructuredVerifierReport(fencedJson);

  assert.equal(report.ok, true, JSON.stringify(report, null, 2));
  assert.equal(report.verdict, "PASS");
});

test("structured verifier validator reports json parse errors explicitly", () => {
  const report = validateStructuredVerifierReport('{"schemaVersion":"structured-verifier-v1"');

  assert.equal(report.ok, false, JSON.stringify(report, null, 2));
  assert.equal(typeof report.parseError, "string");
  assert.notEqual(report.parseError, "");
});

test("structured verifier markdown renderer matches the golden fixture", () => {
  const rendered = renderStructuredVerifierMarkdown(
    readFileSync(fixturePath("structured-verifier-valid.json"), "utf8"),
  );
  const expected = readFileSync(
    fixturePath("structured-verifier-rendered-valid.md"),
    "utf8",
  );

  assert.equal(rendered, expected);
});

test("structured verifier retry prompt reinforces JSON-only output", () => {
  const retryPrompt = buildRetryPrompt("Base prompt", {
    kind: "verifier",
    structuredOutput: true,
    attempt: 2,
    reason: "previous attempt returned malformed JSON",
  });

  assert.match(retryPrompt, /Return JSON only/);
  assert.match(retryPrompt, /Do not wrap the JSON in markdown fences/);
  assert.match(retryPrompt, /schemaVersion: "structured-verifier-v1"/);
});
