# Codex Prompt — Unit 4: Ingestion Lanes

> **Depends on**: Unit 3 (Bootstrap Namespace) must be complete.

## Context

You are working in the `obsidian-kb-local` companion repo at:
```
C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins\obsidian-kb-local\
```

The Vault namespace `08-AI知识库/10-raw/` has four ingestion lanes:
- `web/` — Web Clipper or web article captures
- `papers/` — Academic paper metadata and abstracts
- `repos/` — Repository manifests and summaries
- `manual/` — Hand-written notes, interview transcripts, draft ideas

Each lane has its own ingestion pattern, but all notes must comply with the v2 raw frontmatter contract. The `frontmatter.mjs` module (from Unit 1) provides `generateFrontmatter("raw", fields)` and `validateRawFrontmatter()`.

## Task

### Part A — Create ingestion helper `src/ingest.mjs`

**Create** `obsidian-kb-local/src/ingest.mjs`:

```js
import path from "node:path";
import { generateFrontmatter } from "./frontmatter.mjs";
import { assertWithinBoundary } from "./boundary.mjs";
import { writeNote } from "./note-writer.mjs";

/**
 * Ingest a raw note into the appropriate lane.
 *
 * @param {object} config - vault config from loadConfig()
 * @param {object} params
 * @param {string} params.sourceType - web_article | paper | repo | manual
 * @param {string} params.topic - topic name
 * @param {string} params.sourceUrl - source URL (empty for manual)
 * @param {string} params.title - note title
 * @param {string} params.body - note body content (markdown)
 * @param {object} options - { allowFilesystemFallback, preferCli }
 * @returns {{ mode: string, path: string }}
 */
export function ingestRawNote(config, params, options = {}) {
  const { sourceType, topic, sourceUrl = "", title, body } = params;

  const laneMap = {
    web_article: "web",
    paper: "papers",
    repo: "repos",
    manual: "manual"
  };

  const lane = laneMap[sourceType];
  if (!lane) {
    throw new Error(`Unknown source_type: ${sourceType}. Must be one of: ${Object.keys(laneMap).join(", ")}`);
  }

  // Generate filename from title (sanitize for filesystem)
  const safeName = sanitizeFilename(title);
  const notePath = `${config.machineRoot}/10-raw/${lane}/${safeName}.md`;

  // Boundary check (note-writer also checks, but fail-fast here for better error messages)
  assertWithinBoundary(notePath, config.machineRoot);

  // Generate v2-compliant frontmatter
  const frontmatter = generateFrontmatter("raw", {
    source_type: sourceType,
    topic,
    source_url: sourceUrl,
    status: "queued"
  });

  const content = `${frontmatter}

# ${title}

${body}
`;

  return writeNote(config, { path: notePath, content }, {
    allowFilesystemFallback: options.allowFilesystemFallback ?? true,
    preferCli: options.preferCli ?? true
  });
}

/**
 * Sanitize a string for use as a filename.
 * Removes/replaces characters that are invalid in Windows/Unix filenames.
 */
function sanitizeFilename(name) {
  return name
    .replace(/[<>:"/\\|?*]/g, "")   // Remove Windows-invalid chars
    .replace(/\s+/g, "-")            // Spaces → hyphens
    .replace(/-+/g, "-")             // Collapse multiple hyphens
    .replace(/^-|-$/g, "")           // Trim leading/trailing hyphens
    .slice(0, 100);                  // Cap length
}
```

### Part B — Create `scripts/ingest-web.mjs`

**Create** `obsidian-kb-local/scripts/ingest-web.mjs`:

A CLI script for ingesting web articles. Usage:
```
node scripts/ingest-web.mjs --topic "LLM Agents" --url "https://example.com/article" --title "Article Title"
```

```js
import { loadConfig } from "../src/config.mjs";
import { ingestRawNote } from "../src/ingest.mjs";

const args = process.argv.slice(2);

function getArg(name) {
  const idx = args.indexOf(`--${name}`);
  if (idx === -1 || idx + 1 >= args.length) return null;
  return args[idx + 1];
}

const topic = getArg("topic");
const url = getArg("url") || "";
const title = getArg("title");

if (!topic || !title) {
  console.error("Usage: node scripts/ingest-web.mjs --topic <topic> --url <url> --title <title>");
  console.error("  --topic (required): Topic name");
  console.error("  --url (optional): Source URL");
  console.error("  --title (required): Note title");
  console.error("");
  console.error("Body content is read from stdin. Pipe or type, then Ctrl+D (Unix) or Ctrl+Z (Windows).");
  process.exit(1);
}

// Read body from stdin
let body = "";
if (!process.stdin.isTTY) {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  body = Buffer.concat(chunks).toString("utf8");
} else {
  body = "(No content provided — add content manually)";
}

const config = loadConfig();
const result = ingestRawNote(config, {
  sourceType: "web_article",
  topic,
  sourceUrl: url,
  title,
  body
}, { allowFilesystemFallback: true });

console.log(`✓ Ingested: ${result.path} (mode: ${result.mode})`);
```

### Part C — Add npm script

**Modify** `obsidian-kb-local/package.json` — add to `"scripts"`:
```json
"ingest-web": "node scripts/ingest-web.mjs"
```

### Part D — Create `tests/ingest.test.mjs`

**Create** `obsidian-kb-local/tests/ingest.test.mjs`:

```js
import { describe, it } from "node:test";
import assert from "node:assert/strict";

// We can't easily test ingestRawNote without a real config/vault,
// so test the sanitizeFilename logic by importing and testing the module's behavior

describe("ingest module", () => {
  it("can be imported without error", async () => {
    // Dynamic import to verify module syntax is correct
    const mod = await import("../src/ingest.mjs");
    assert.equal(typeof mod.ingestRawNote, "function");
  });
});
```

This is a thin integration test — the real validation happens via the frontmatter and boundary modules (tested in Units 0 and 1).

## Acceptance Criteria

1. `ingest.mjs` exports `ingestRawNote()` function
2. Ingested notes use `generateFrontmatter("raw", ...)` — all v2 fields present
3. Ingested notes land in the correct lane subdirectory (`web/`, `papers/`, `repos/`, `manual/`)
4. Boundary check runs before any write operation
5. Filenames are sanitized (no Windows-invalid chars, spaces → hyphens)
6. `ingest-web.mjs` script works: `echo "test content" | cmd /c "cd obsidian-kb-local && node scripts/ingest-web.mjs --topic test --title test-article"`
7. All existing tests still pass

## Safety Constraints

- All writes go through `writeNote()` which has `assertWithinBoundary()` guard
- Do NOT install new npm dependencies
- `ingestRawNote()` defaults to `allowFilesystemFallback: true` for Windows CLI compatibility
