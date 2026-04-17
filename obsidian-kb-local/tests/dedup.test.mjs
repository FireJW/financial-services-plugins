import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, it } from "node:test";
import { findExistingByDedupKey, generateDedupKey } from "../src/dedup.mjs";

describe("generateDedupKey", () => {
  it("generates a normalized key", () => {
    const key = generateDedupKey("LLM Agents", "concept", "https://example.com/agents");
    assert.equal(key, "llm agents::concept::https://example.com/agents");
  });

  it("normalizes case", () => {
    const left = generateDedupKey("LLM Agents", "Concept", "HTTPS://EXAMPLE.COM");
    const right = generateDedupKey("llm agents", "concept", "https://example.com");
    assert.equal(left, right);
  });

  it("allows empty source URL", () => {
    assert.equal(generateDedupKey("topic", "synthesis", ""), "topic::synthesis::");
  });

  it("throws on empty topic", () => {
    assert.throws(() => generateDedupKey("", "concept", "url"), /topic/);
  });

  it("throws on empty wikiKind", () => {
    assert.throws(() => generateDedupKey("topic", "", "url"), /wikiKind/);
  });
});

describe("findExistingByDedupKey", () => {
  it("finds an existing note by dedup key", () => {
    const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "dedup-test-"));
    try {
      const wikiDirectory = path.join(tempDirectory, "08-AI知识库", "20-wiki", "concepts");
      fs.mkdirSync(wikiDirectory, { recursive: true });

      const content = `---
kb_type: "wiki"
wiki_kind: "concept"
topic: "Test Topic"
dedup_key: "test topic::concept::https://example.com"
---

# Test Topic
`;
      fs.writeFileSync(path.join(wikiDirectory, "test-topic.md"), content, "utf8");

      const result = findExistingByDedupKey(
        tempDirectory,
        "08-AI知识库",
        "test topic::concept::https://example.com"
      );
      assert.equal(result, "08-AI知识库/20-wiki/concepts/test-topic.md");
    } finally {
      fs.rmSync(tempDirectory, { recursive: true, force: true });
    }
  });

  it("returns null when no match exists", () => {
    const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "dedup-test-"));
    try {
      fs.mkdirSync(path.join(tempDirectory, "08-AI知识库", "20-wiki"), {
        recursive: true
      });
      assert.equal(
        findExistingByDedupKey(tempDirectory, "08-AI知识库", "missing::concept::"),
        null
      );
    } finally {
      fs.rmSync(tempDirectory, { recursive: true, force: true });
    }
  });

  it("returns null when the wiki directory is missing", () => {
    assert.equal(
      findExistingByDedupKey(path.join(os.tmpdir(), "missing-vault"), "08-AI知识库", "key"),
      null
    );
  });
});
