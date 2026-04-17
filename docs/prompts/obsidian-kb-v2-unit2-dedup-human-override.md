# Codex Prompt — Unit 2: Dedup and Human-Override Preservation

> **Depends on**: Unit 1 (Frontmatter Enforcement) must be complete.

## Context

You are working in the `obsidian-kb-local` companion repo at:
```
C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins\obsidian-kb-local\
```

The compile pipeline (Unit 5) will generate wiki notes from raw sources. Two critical requirements:

1. **Dedup**: When recompiling a source, the system must detect if a wiki note already exists for the same `topic + wiki_kind + source_url` combination and overwrite it instead of creating a duplicate.
2. **Human-override preservation**: Users can add `<!-- human-override -->...<!-- /human-override -->` blocks in wiki notes. These blocks MUST survive recompilation.

The dedup key format is: `topic::wiki_kind::primary_source_url`

## Task

### Part A — Create `src/dedup.mjs`

**Create** `obsidian-kb-local/src/dedup.mjs`:

```js
import fs from "node:fs";
import path from "node:path";
import { parseFrontmatter } from "./frontmatter.mjs";

/**
 * Generate a dedup key from topic, wiki_kind, and source URL.
 * All components are lowercased and trimmed for consistent matching.
 */
export function generateDedupKey(topic, wikiKind, sourceUrl) {
  const t = (topic || "").trim().toLowerCase();
  const k = (wikiKind || "").trim().toLowerCase();
  const u = (sourceUrl || "").trim().toLowerCase();

  if (!t || !k) {
    throw new Error("generateDedupKey requires non-empty topic and wikiKind");
  }

  return `${t}::${k}::${u}`;
}

/**
 * Search for an existing wiki note with a matching dedup key.
 * Scans all .md files under vaultPath/machineRoot/20-wiki/.
 *
 * Returns the relative path (from vault root) if found, null otherwise.
 */
export function findExistingByDedupKey(vaultPath, machineRoot, dedupKey) {
  const wikiDir = path.join(vaultPath, machineRoot, "20-wiki");

  if (!fs.existsSync(wikiDir)) {
    return null;
  }

  const normalizedKey = dedupKey.toLowerCase();
  const files = walkMarkdownFiles(wikiDir);

  for (const filePath of files) {
    const content = fs.readFileSync(filePath, "utf8");
    const fm = parseFrontmatter(content);

    if (fm && typeof fm.dedup_key === "string") {
      if (fm.dedup_key.toLowerCase() === normalizedKey) {
        // Return path relative to vault root
        const relative = path.relative(vaultPath, filePath).replace(/\\/g, "/");
        return relative;
      }
    }
  }

  return null;
}

/**
 * Recursively walk a directory and return all .md file paths.
 */
function walkMarkdownFiles(dir) {
  const results = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkMarkdownFiles(fullPath));
    } else if (entry.name.endsWith(".md")) {
      results.push(fullPath);
    }
  }

  return results;
}
```

### Part B — Create `src/human-override.mjs`

**Create** `obsidian-kb-local/src/human-override.mjs`:

```js
/**
 * Extract and preserve human-override blocks during wiki note recompilation.
 *
 * Human-override blocks use the format:
 *   <!-- human-override -->
 *   ... user content that survives recompile ...
 *   <!-- /human-override -->
 *
 * Multiple override blocks per note are supported.
 */

const OVERRIDE_RE = /<!-- human-override -->([\s\S]*?)<!-- \/human-override -->/g;

/**
 * Extract all human-override blocks from content.
 * Returns an array of { fullMatch, innerContent, index } objects.
 */
export function extractHumanOverrides(content) {
  if (!content || typeof content !== "string") {
    return [];
  }

  const overrides = [];
  let match;

  // Reset regex state
  OVERRIDE_RE.lastIndex = 0;

  while ((match = OVERRIDE_RE.exec(content)) !== null) {
    overrides.push({
      fullMatch: match[0],
      innerContent: match[1],
      index: match.index
    });
  }

  return overrides;
}

/**
 * Merge new LLM-generated content with existing human-override blocks.
 *
 * Strategy:
 * 1. Extract overrides from the existing (old) content
 * 2. If the new content already contains human-override blocks, preserve them as-is
 * 3. If the new content does NOT contain human-override blocks, append the old ones
 *    at the end of the new content
 *
 * This ensures human edits are never lost during recompilation.
 */
export function mergeWithOverrides(newContent, existingOverrides) {
  if (!existingOverrides || existingOverrides.length === 0) {
    return newContent;
  }

  // Check if new content already has override blocks
  OVERRIDE_RE.lastIndex = 0;
  const newHasOverrides = OVERRIDE_RE.test(newContent);

  if (newHasOverrides) {
    // New content has its own overrides — trust the LLM output
    // (This should rarely happen if the LLM prompt is correct)
    return newContent;
  }

  // Append existing override blocks at the end
  const overrideSection = existingOverrides
    .map(o => o.fullMatch)
    .join("\n\n");

  return `${newContent.trimEnd()}\n\n${overrideSection}\n`;
}

/**
 * Check if content has any human-override blocks.
 */
export function hasHumanOverrides(content) {
  if (!content || typeof content !== "string") {
    return false;
  }
  OVERRIDE_RE.lastIndex = 0;
  return OVERRIDE_RE.test(content);
}
```

### Part C — Create `tests/dedup.test.mjs`

**Create** `obsidian-kb-local/tests/dedup.test.mjs`:

```js
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { generateDedupKey, findExistingByDedupKey } from "../src/dedup.mjs";

describe("generateDedupKey", () => {
  it("generates key from topic, kind, and URL", () => {
    const key = generateDedupKey("LLM Agents", "concept", "https://example.com/agents");
    assert.equal(key, "llm agents::concept::https://example.com/agents");
  });

  it("normalizes case", () => {
    const k1 = generateDedupKey("LLM Agents", "Concept", "HTTPS://EXAMPLE.COM");
    const k2 = generateDedupKey("llm agents", "concept", "https://example.com");
    assert.equal(k1, k2);
  });

  it("allows empty source URL", () => {
    const key = generateDedupKey("topic", "synthesis", "");
    assert.equal(key, "topic::synthesis::");
  });

  it("throws on empty topic", () => {
    assert.throws(() => generateDedupKey("", "concept", "url"), /topic/);
  });

  it("throws on empty wikiKind", () => {
    assert.throws(() => generateDedupKey("topic", "", "url"), /wikiKind/);
  });
});

describe("findExistingByDedupKey", () => {
  it("finds existing note by dedup key", () => {
    // Create a temp directory structure
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "dedup-test-"));
    const wikiDir = path.join(tmpDir, "08-AI知识库", "20-wiki", "concepts");
    fs.mkdirSync(wikiDir, { recursive: true });

    const noteContent = `---
kb_type: "wiki"
wiki_kind: "concept"
topic: "Test Topic"
dedup_key: "test topic::concept::https://example.com"
---

# Test Topic
`;
    fs.writeFileSync(path.join(wikiDir, "test-topic.md"), noteContent, "utf8");

    const result = findExistingByDedupKey(tmpDir, "08-AI知识库", "test topic::concept::https://example.com");
    assert.ok(result);
    assert.ok(result.includes("20-wiki/concepts/test-topic.md"));

    // Cleanup
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("returns null when no match", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "dedup-test-"));
    const wikiDir = path.join(tmpDir, "08-AI知识库", "20-wiki");
    fs.mkdirSync(wikiDir, { recursive: true });

    const result = findExistingByDedupKey(tmpDir, "08-AI知识库", "nonexistent::key::here");
    assert.equal(result, null);

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("returns null when wiki dir does not exist", () => {
    const result = findExistingByDedupKey("/nonexistent", "08-AI知识库", "key");
    assert.equal(result, null);
  });
});
```

### Part D — Create `tests/human-override.test.mjs`

**Create** `obsidian-kb-local/tests/human-override.test.mjs`:

```js
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  extractHumanOverrides,
  mergeWithOverrides,
  hasHumanOverrides
} from "../src/human-override.mjs";

describe("extractHumanOverrides", () => {
  it("extracts single override block", () => {
    const content = `# Title

Some content

<!-- human-override -->
My custom note that should survive recompile.
<!-- /human-override -->

More content`;

    const overrides = extractHumanOverrides(content);
    assert.equal(overrides.length, 1);
    assert.ok(overrides[0].innerContent.includes("My custom note"));
  });

  it("extracts multiple override blocks", () => {
    const content = `# Title

<!-- human-override -->
Block 1
<!-- /human-override -->

Middle content

<!-- human-override -->
Block 2
<!-- /human-override -->`;

    const overrides = extractHumanOverrides(content);
    assert.equal(overrides.length, 2);
    assert.ok(overrides[0].innerContent.includes("Block 1"));
    assert.ok(overrides[1].innerContent.includes("Block 2"));
  });

  it("returns empty array for content without overrides", () => {
    const overrides = extractHumanOverrides("# Just normal content");
    assert.equal(overrides.length, 0);
  });

  it("returns empty array for null/undefined", () => {
    assert.equal(extractHumanOverrides(null).length, 0);
    assert.equal(extractHumanOverrides(undefined).length, 0);
  });
});

describe("mergeWithOverrides", () => {
  it("appends existing overrides to new content", () => {
    const newContent = "# Updated Title\n\nNew LLM-generated content.";
    const existingOverrides = [
      {
        fullMatch: "<!-- human-override -->\nMy custom note\n<!-- /human-override -->",
        innerContent: "\nMy custom note\n",
        index: 100
      }
    ];

    const merged = mergeWithOverrides(newContent, existingOverrides);
    assert.ok(merged.includes("New LLM-generated content"));
    assert.ok(merged.includes("My custom note"));
    assert.ok(merged.includes("<!-- human-override -->"));
  });

  it("returns new content unchanged if no overrides", () => {
    const newContent = "# Title\n\nContent.";
    const merged = mergeWithOverrides(newContent, []);
    assert.equal(merged, newContent);
  });

  it("preserves new content overrides if present", () => {
    const newContent = `# Title

<!-- human-override -->
Already has override
<!-- /human-override -->`;

    const existingOverrides = [
      {
        fullMatch: "<!-- human-override -->\nOld override\n<!-- /human-override -->",
        innerContent: "\nOld override\n",
        index: 0
      }
    ];

    const merged = mergeWithOverrides(newContent, existingOverrides);
    assert.ok(merged.includes("Already has override"));
    // Should NOT have the old override appended
    assert.ok(!merged.includes("Old override"));
  });
});

describe("hasHumanOverrides", () => {
  it("returns true for content with overrides", () => {
    assert.ok(hasHumanOverrides("text <!-- human-override -->x<!-- /human-override --> end"));
  });

  it("returns false for content without overrides", () => {
    assert.ok(!hasHumanOverrides("# Just normal content"));
  });

  it("returns false for null", () => {
    assert.ok(!hasHumanOverrides(null));
  });
});
```

## Acceptance Criteria

1. Run `cmd /c "cd obsidian-kb-local && node --test tests/dedup.test.mjs"` — all tests pass
2. Run `cmd /c "cd obsidian-kb-local && node --test tests/human-override.test.mjs"` — all tests pass
3. `generateDedupKey()` normalizes case for consistent matching
4. `findExistingByDedupKey()` scans only `20-wiki/` subdirectory
5. `extractHumanOverrides()` correctly handles 0, 1, or multiple override blocks
6. `mergeWithOverrides()` appends old overrides only if new content lacks them
7. All existing tests still pass

## Safety Constraints

- Do NOT modify any Vault files
- Do NOT install new npm dependencies
- `findExistingByDedupKey()` is READ-ONLY — it must never write or modify files
- Temp directories in tests must be cleaned up after each test
