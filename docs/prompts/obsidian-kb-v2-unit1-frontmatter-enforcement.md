# Codex Prompt — Unit 1: Frontmatter Enforcement Layer

> **Depends on**: Unit 0 (Safety Lockdown) must be complete.

## Context

You are working in the `obsidian-kb-local` companion repo at:
```
C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins\obsidian-kb-local\
```

The knowledge base uses YAML frontmatter to track note metadata. The v2 plan defines a strict contract for frontmatter fields. Currently:
- `templates/raw-note.md` and `templates/wiki-note.md` have basic frontmatter but are missing v2 fields (`kb_date`, `kb_source_count`, `dedup_key`)
- `bootstrap-plan.mjs` generates notes with `new Date().toISOString()` for timestamps — no timezone offset, no `kb_date` field
- Dataview queries need `kb_date` in `YYYY-MM-DD` format for native date comparisons
- `captured_at` / `compiled_at` must be ISO 8601 with timezone: `YYYY-MM-DDTHH:mm:ss+08:00`

## Task

### Part A — Create `src/frontmatter.mjs`

**Create** `obsidian-kb-local/src/frontmatter.mjs`:

```js
/**
 * Frontmatter parsing, validation, and generation for KB notes.
 *
 * Enforces the v2 frontmatter contract:
 * - captured_at / compiled_at: ISO 8601 with timezone offset
 * - kb_date: YYYY-MM-DD (Dataview native date format)
 * - All enum fields validated against allowed values
 */

const RAW_SOURCE_TYPES = ["web_article", "paper", "repo", "manual"];
const RAW_STATUSES = ["queued", "compiled", "archived", "error"];
const WIKI_KINDS = ["concept", "entity", "source", "synthesis"];
const WIKI_REVIEW_STATES = ["draft", "reviewed"];
const MANAGED_BY_VALUES = ["human", "codex"];

// ISO 8601 with timezone offset: 2026-04-04T15:00:00+08:00
const ISO_8601_TZ_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/;
// YYYY-MM-DD
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Parse YAML frontmatter from markdown content.
 * Returns null if no frontmatter found.
 */
export function parseFrontmatter(content) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return null;

  const yaml = match[1];
  const result = {};

  for (const line of yaml.split(/\r?\n/)) {
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;

    const key = line.slice(0, colonIdx).trim();
    let value = line.slice(colonIdx + 1).trim();

    // Handle quoted strings
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }

    // Handle arrays (simple single-line format: [a, b])
    if (value.startsWith("[") && value.endsWith("]")) {
      value = value.slice(1, -1).split(",").map(s => s.trim().replace(/^["']|["']$/g, "")).filter(Boolean);
    }

    // Handle numbers
    if (/^\d+$/.test(value)) {
      value = parseInt(value, 10);
    }

    result[key] = value;
  }

  return result;
}

/**
 * Validate frontmatter for a raw note. Throws on invalid fields.
 */
export function validateRawFrontmatter(fm) {
  if (!fm || typeof fm !== "object") {
    throw new Error("Frontmatter is missing or not an object");
  }

  assertField(fm, "kb_type", "raw");
  assertEnum(fm, "source_type", RAW_SOURCE_TYPES);
  assertPresent(fm, "topic");
  assertPresent(fm, "source_url");
  assertIso8601Tz(fm, "captured_at");
  assertDateField(fm, "kb_date");
  assertEnum(fm, "status", RAW_STATUSES);
  assertField(fm, "managed_by", "human");
}

/**
 * Validate frontmatter for a wiki note. Throws on invalid fields.
 */
export function validateWikiFrontmatter(fm) {
  if (!fm || typeof fm !== "object") {
    throw new Error("Frontmatter is missing or not an object");
  }

  assertField(fm, "kb_type", "wiki");
  assertEnum(fm, "wiki_kind", WIKI_KINDS);
  assertPresent(fm, "topic");
  assertArray(fm, "compiled_from");
  assertIso8601Tz(fm, "compiled_at");
  assertDateField(fm, "kb_date");
  assertEnum(fm, "review_state", WIKI_REVIEW_STATES);
  assertField(fm, "managed_by", "codex");
  assertNumber(fm, "kb_source_count");
  assertPresent(fm, "dedup_key");
}

/**
 * Generate a YAML frontmatter string from type and fields.
 * Automatically sets kb_date from the timestamp field.
 */
export function generateFrontmatter(type, fields = {}) {
  const now = formatIso8601Tz(new Date());
  const today = now.slice(0, 10);

  if (type === "raw") {
    return formatYaml({
      kb_type: "raw",
      source_type: fields.source_type || "manual",
      topic: fields.topic || "",
      source_url: fields.source_url || "",
      captured_at: fields.captured_at || now,
      kb_date: fields.kb_date || today,
      status: fields.status || "queued",
      managed_by: "human"
    });
  }

  if (type === "wiki") {
    return formatYaml({
      kb_type: "wiki",
      wiki_kind: fields.wiki_kind || "concept",
      topic: fields.topic || "",
      compiled_from: fields.compiled_from || [],
      compiled_at: fields.compiled_at || now,
      kb_date: fields.kb_date || today,
      review_state: fields.review_state || "draft",
      managed_by: "codex",
      kb_source_count: fields.kb_source_count ?? 0,
      dedup_key: fields.dedup_key || ""
    });
  }

  throw new Error(`Unknown frontmatter type: ${type}`);
}

/**
 * Format a Date object as ISO 8601 with +08:00 timezone offset.
 */
export function formatIso8601Tz(date, offsetHours = 8) {
  const offset = offsetHours * 60;
  const local = new Date(date.getTime() + offset * 60 * 1000);
  const iso = local.toISOString().replace("Z", "");
  const sign = offsetHours >= 0 ? "+" : "-";
  const absH = String(Math.abs(offsetHours)).padStart(2, "0");
  return `${iso.slice(0, 19)}${sign}${absH}:00`;
}

// --- Internal helpers ---

function formatYaml(obj) {
  const lines = ["---"];
  for (const [key, value] of Object.entries(obj)) {
    if (Array.isArray(value)) {
      lines.push(`${key}: [${value.map(v => `"${v}"`).join(", ")}]`);
    } else if (typeof value === "number") {
      lines.push(`${key}: ${value}`);
    } else {
      lines.push(`${key}: "${value}"`);
    }
  }
  lines.push("---");
  return lines.join("\n");
}

function assertField(fm, key, expected) {
  if (fm[key] !== expected) {
    throw new Error(`Frontmatter field "${key}" must be "${expected}", got "${fm[key]}"`);
  }
}

function assertEnum(fm, key, allowed) {
  if (!allowed.includes(fm[key])) {
    throw new Error(`Frontmatter field "${key}" must be one of [${allowed.join(", ")}], got "${fm[key]}"`);
  }
}

function assertPresent(fm, key) {
  if (fm[key] === undefined || fm[key] === null) {
    throw new Error(`Frontmatter field "${key}" is required but missing`);
  }
}

function assertIso8601Tz(fm, key) {
  assertPresent(fm, key);
  if (typeof fm[key] !== "string" || !ISO_8601_TZ_RE.test(fm[key])) {
    throw new Error(
      `Frontmatter field "${key}" must be ISO 8601 with timezone (YYYY-MM-DDTHH:mm:ss+HH:MM), got "${fm[key]}"`
    );
  }
}

function assertDateField(fm, key) {
  assertPresent(fm, key);
  const value = String(fm[key]);
  if (!DATE_RE.test(value)) {
    throw new Error(
      `Frontmatter field "${key}" must be YYYY-MM-DD, got "${fm[key]}"`
    );
  }
}

function assertArray(fm, key) {
  assertPresent(fm, key);
  if (!Array.isArray(fm[key])) {
    throw new Error(`Frontmatter field "${key}" must be an array, got ${typeof fm[key]}`);
  }
}

function assertNumber(fm, key) {
  assertPresent(fm, key);
  if (typeof fm[key] !== "number" || !Number.isFinite(fm[key])) {
    throw new Error(`Frontmatter field "${key}" must be a number, got "${fm[key]}"`);
  }
}
```

### Part B — Create `tests/frontmatter.test.mjs`

**Create** `obsidian-kb-local/tests/frontmatter.test.mjs`:

```js
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  parseFrontmatter,
  validateRawFrontmatter,
  validateWikiFrontmatter,
  generateFrontmatter,
  formatIso8601Tz
} from "../src/frontmatter.mjs";

describe("parseFrontmatter", () => {
  it("parses valid YAML frontmatter", () => {
    const content = `---\nkb_type: "raw"\ntopic: "test"\n---\n\n# Body`;
    const fm = parseFrontmatter(content);
    assert.equal(fm.kb_type, "raw");
    assert.equal(fm.topic, "test");
  });

  it("returns null for content without frontmatter", () => {
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

  it("rejects missing kb_type", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, kb_type: undefined }),
      /kb_type/
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

  it("rejects malformed captured_at (no timezone)", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, captured_at: "2026-04-04T15:00:00Z" }),
      /captured_at.*ISO 8601/
    );
  });

  it("rejects malformed captured_at (plain date)", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, captured_at: "2026-04-04" }),
      /captured_at.*ISO 8601/
    );
  });

  it("rejects malformed kb_date", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, kb_date: "04/04/2026" }),
      /kb_date.*YYYY-MM-DD/
    );
  });

  it("rejects invalid status", () => {
    assert.throws(
      () => validateRawFrontmatter({ ...validRaw, status: "pending" }),
      /status/
    );
  });

  it("rejects managed_by != human", () => {
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
    dedup_key: "test topic::concept::https://example.com"
  };

  it("accepts valid wiki frontmatter", () => {
    assert.doesNotThrow(() => validateWikiFrontmatter(validWiki));
  });

  it("rejects missing wiki_kind", () => {
    assert.throws(
      () => validateWikiFrontmatter({ ...validWiki, wiki_kind: undefined }),
      /wiki_kind/
    );
  });

  it("rejects compiled_from as string instead of array", () => {
    assert.throws(
      () => validateWikiFrontmatter({ ...validWiki, compiled_from: "a string" }),
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
  it("generates valid raw frontmatter", () => {
    const yaml = generateFrontmatter("raw", {
      source_type: "web_article",
      topic: "test",
      source_url: "https://example.com"
    });
    assert.ok(yaml.startsWith("---"));
    assert.ok(yaml.endsWith("---"));
    assert.ok(yaml.includes('kb_type: "raw"'));
    assert.ok(yaml.includes('kb_date:'));
    assert.ok(yaml.includes('managed_by: "human"'));
  });

  it("generates valid wiki frontmatter", () => {
    const yaml = generateFrontmatter("wiki", {
      wiki_kind: "source",
      topic: "test",
      dedup_key: "test::source::url"
    });
    assert.ok(yaml.includes('kb_type: "wiki"'));
    assert.ok(yaml.includes('managed_by: "codex"'));
    assert.ok(yaml.includes("kb_source_count: 0"));
  });

  it("throws on unknown type", () => {
    assert.throws(() => generateFrontmatter("unknown"), /Unknown frontmatter type/);
  });
});

describe("formatIso8601Tz", () => {
  it("produces +08:00 offset", () => {
    const result = formatIso8601Tz(new Date("2026-04-04T07:00:00Z"), 8);
    assert.ok(result.endsWith("+08:00"));
    assert.ok(result.startsWith("2026-04-04T15:00:00"));
  });
});
```

### Part C — Update templates

**Replace** `obsidian-kb-local/templates/raw-note.md` with:
```markdown
---
kb_type: raw
source_type: manual
topic: ""
source_url: ""
captured_at: ""
kb_date: ""
status: queued
managed_by: human
---

# Title

## Summary

## Source Notes

## Next Questions
```

**Replace** `obsidian-kb-local/templates/wiki-note.md` with:
```markdown
---
kb_type: wiki
wiki_kind: concept
topic: ""
compiled_from: []
compiled_at: ""
kb_date: ""
review_state: draft
managed_by: codex
kb_source_count: 0
dedup_key: ""
---

# Title

## One-line summary

## Key points

## Source links

## Open questions
```

### Part D — Update bootstrap-plan.mjs

In `obsidian-kb-local/src/bootstrap-plan.mjs`, update the contract notes and pilot topic to use v2 frontmatter fields:

1. Import `formatIso8601Tz` from `./frontmatter.mjs`
2. Replace `const now = new Date().toISOString()` with proper timezone-aware timestamp
3. Add `kb_date`, `kb_source_count`, `dedup_key` fields to the pilot topic frontmatter
4. Update the raw and wiki contract notes to include v2 fields
5. Add `prompts/` directory to the directory list under `90-ops`

## Acceptance Criteria

1. Run `cmd /c "cd obsidian-kb-local && node --test tests/frontmatter.test.mjs"` — all tests pass
2. `generateFrontmatter("raw", ...)` produces `captured_at` with `+08:00` timezone
3. `generateFrontmatter("wiki", ...)` produces `kb_source_count`, `dedup_key` fields
4. `validateRawFrontmatter()` throws on ISO timestamps without timezone offset (e.g., `Z` suffix)
5. `validateWikiFrontmatter()` throws on non-array `compiled_from`
6. Templates updated with v2 fields
7. Existing `run-tests.mjs` tests still pass

## Safety Constraints

- Do NOT modify any Vault files — this unit only modifies companion repo files
- Do NOT install new npm dependencies
- All date formatting must use `+08:00` offset (user's timezone is CST/China Standard Time)
