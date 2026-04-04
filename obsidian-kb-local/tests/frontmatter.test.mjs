import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  formatIso8601Tz,
  generateFrontmatter,
  parseFrontmatter,
  validateRawFrontmatter,
  validateWikiFrontmatter
} from "../src/frontmatter.mjs";

describe("parseFrontmatter", () => {
  it("parses valid YAML frontmatter", () => {
    const content = `---\nkb_type: "raw"\ntopic: "test"\n---\n\n# Body`;
    const frontmatter = parseFrontmatter(content);
    assert.equal(frontmatter.kb_type, "raw");
    assert.equal(frontmatter.topic, "test");
  });

  it("returns null when frontmatter is missing", () => {
    assert.equal(parseFrontmatter("# Just a heading"), null);
  });
});

describe("validateRawFrontmatter", () => {
  const validRaw = {
    kb_type: "raw",
    source_type: "web_article",
    topic: "test topic",
    source_url: "https://example.com",
    captured_at: "2026-04-04T15:00:00+08:00",
    kb_date: "2026-04-04",
    status: "queued",
    managed_by: "human"
  };

  it("accepts valid raw frontmatter", () => {
    assert.doesNotThrow(() => validateRawFrontmatter(validRaw));
  });

  it("accepts epub as a valid raw source_type", () => {
    assert.doesNotThrow(() =>
      validateRawFrontmatter({ ...validRaw, source_type: "epub", source_url: "file:///D:/books/test.epub" })
    );
  });

  it("rejects wrong kb_type", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, kb_type: "wiki" }),
      /kb_type/
    );
  });

  it("rejects invalid source_type", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, source_type: "video" }),
      /source_type/
    );
  });

  it("rejects malformed captured_at without timezone offset", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, captured_at: "2026-04-04T15:00:00Z" }),
      /captured_at.*ISO 8601/
    );
  });

  it("rejects malformed kb_date", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, kb_date: "04/04/2026" }),
      /kb_date.*YYYY-MM-DD/
    );
  });

  it("rejects managed_by other than human", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, managed_by: "codex" }),
      /managed_by/
    );
  });
});

describe("validateWikiFrontmatter", () => {
  const validWiki = {
    kb_type: "wiki",
    wiki_kind: "concept",
    topic: "test topic",
    compiled_from: ["08-AI知识库/10-raw/web/test.md"],
    compiled_at: "2026-04-04T15:30:00+08:00",
    kb_date: "2026-04-04",
    review_state: "draft",
    managed_by: "codex",
    kb_source_count: 1,
    dedup_key: "test-topic::concept::https://example.com"
  };

  it("accepts valid wiki frontmatter", () => {
    assert.doesNotThrow(() => validateWikiFrontmatter(validWiki));
  });

  it("rejects compiled_from when it is not an array", () => {
    assert.throws(
      () => validateWikiFrontmatter({ ...validWiki, compiled_from: "not-an-array" }),
      /compiled_from.*array/
    );
  });

  it("rejects non-numeric kb_source_count", () => {
    assert.throws(
      () => validateWikiFrontmatter({ ...validWiki, kb_source_count: "one" }),
      /kb_source_count.*number/
    );
  });
});

describe("generateFrontmatter", () => {
  it("generates valid raw frontmatter with timezone-aware captured_at", () => {
    const yaml = generateFrontmatter("raw", {
      source_type: "web_article",
      topic: "test",
      source_url: "https://example.com"
    });
    assert.ok(yaml.includes('kb_type: "raw"'));
    assert.match(yaml, /captured_at: "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00"/);
    assert.match(yaml, /kb_date: "\d{4}-\d{2}-\d{2}"/);
  });

  it("generates valid wiki frontmatter with v2 fields", () => {
    const yaml = generateFrontmatter("wiki", {
      wiki_kind: "source",
      topic: "test",
      dedup_key: "test::source::url"
    });
    assert.ok(yaml.includes('kb_type: "wiki"'));
    assert.ok(yaml.includes("kb_source_count: 0"));
    assert.ok(yaml.includes('dedup_key: "test::source::url"'));
  });

  it("throws on unknown type", () => {
    assert.throws(() => generateFrontmatter("unknown"), /Unknown frontmatter type/);
  });
});

describe("formatIso8601Tz", () => {
  it("produces +08:00 output", () => {
    const value = formatIso8601Tz(new Date("2026-04-04T07:00:00Z"), 8);
    assert.equal(value, "2026-04-04T15:00:00+08:00");
  });
});
