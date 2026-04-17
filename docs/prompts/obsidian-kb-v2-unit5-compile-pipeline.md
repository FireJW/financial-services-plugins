# Codex Prompt — Unit 5: Compile Pipeline

> **Depends on**: Unit 2 (Dedup + Human-Override), Unit 4 (Ingestion Lanes) must be complete.

## Context

You are working in the `obsidian-kb-local` companion repo at:
```
C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins\obsidian-kb-local\
```

The Vault is at `D:\OneDrive - zn\文档\Obsidian Vault`, config.machineRoot = `08-AI知识库`.

This unit implements the core LLM compile pipeline: raw notes → wiki notes. The pipeline:
1. Reads raw notes for a target topic from `10-raw/`
2. Checks for existing wiki notes via dedup key
3. Calls LLM with prompt template + raw content
4. Parses LLM output into individual note objects
5. For each note: dedup check → merge with human-override preservation → write
6. Updates raw note `status` from `queued` to `compiled`
7. Logs compile events to `logs/` (in companion repo, NOT Vault)

**LLM call contract**:
- Provider: Codex (via local LLM wrapper or API)
- Timeout: 120 seconds per source
- Retry: 1 retry on failure
- Fallback: if LLM call fails, mark raw note `status: error` and continue

## Task

### Part A — Create prompt templates

**Create** `obsidian-kb-local/prompts/compile-source.md`:

```markdown
# Compile Source Prompt

You are a knowledge base compiler. Given a raw note, produce structured wiki notes.

## Input

- Raw note content (full text, provided below)
- Raw note frontmatter (source_type, topic, source_url)
- Existing wiki notes for the same topic (titles + frontmatter only, for dedup)

## Output Format

Return a JSON array of note objects. Each object has:
```json
{
  "wiki_kind": "source | concept | entity",
  "title": "Note Title",
  "topic": "same as input topic",
  "body": "Markdown body content (no frontmatter)",
  "source_url": "from raw note"
}
```

## Rules

1. ALWAYS produce exactly ONE `source` wiki note summarizing the raw material
2. Produce zero or more `concept` notes for new concepts extracted
3. Produce zero or more `entity` notes for named entities (people, companies, tools)
4. Never fabricate URLs or citations not present in the raw note
5. If a concept wiki note already exists (listed in existing notes), output ONLY new sections to append
6. Maximum 500 words per source summary
7. Maximum 300 words per concept/entity note
8. Use clear, factual language — no speculation
9. Output valid JSON only — no markdown fences around the JSON

## Raw Note

{{RAW_CONTENT}}

## Existing Wiki Notes for Topic "{{TOPIC}}"

{{EXISTING_NOTES}}
```

**Create** `obsidian-kb-local/prompts/rebuild-topic.md`:

```markdown
# Rebuild Topic Prompt

You are a knowledge base compiler. Given all raw and wiki notes for a topic, produce an updated synthesis.

## Input

- Topic name
- All raw notes with matching topic (full text)
- All existing wiki notes with matching topic (full text)

## Output Format

Return a JSON array of note objects to update. Each object has:
```json
{
  "wiki_kind": "synthesis | concept | entity | source",
  "title": "Note Title",
  "topic": "topic name",
  "body": "Full updated markdown body (no frontmatter)",
  "action": "create | update | no_change"
}
```

## Rules

1. Preserve any <!-- human-override --> sections EXACTLY as they appear
2. Update compiled_at timestamp to now
3. Update kb_source_count to reflect total raw sources
4. If no new information compared to existing wiki notes, set action to "no_change"
5. For updates, provide the COMPLETE new body (not a diff)
6. Maximum 1000 words per synthesis note
7. Output valid JSON only
```

**Create** `obsidian-kb-local/prompts/health-check-report.md`:

```markdown
# Health Check Report Prompt

Analyze the knowledge base for issues.

## Input

- List of all wiki notes with frontmatter
- List of all raw notes with frontmatter

## Output Format (JSON)

```json
{
  "orphan_wiki": ["list of wiki notes with no compiled_from match"],
  "stale_wiki": ["wiki notes where compiled_at is older than newest raw note for same topic"],
  "missing_source": ["wiki notes where compiled_from points to non-existent raw note"],
  "contract_violations": ["notes with missing/malformed frontmatter fields"],
  "dedup_conflicts": ["multiple wiki notes with same dedup_key"],
  "summary": "One paragraph summary of KB health"
}
```

## Rules

1. Be thorough — check every note
2. Report exact file paths for each issue
3. Include severity (critical, warning, info) for each finding
4. Output valid JSON only
```

### Part B — Create `scripts/compile-source.mjs`

**Create** `obsidian-kb-local/scripts/compile-source.mjs`:

```js
#!/usr/bin/env node

/**
 * Compile raw notes for a topic into wiki notes.
 *
 * Usage:
 *   node scripts/compile-source.mjs --topic "LLM Agents"
 *   node scripts/compile-source.mjs --file "08-AI知识库/10-raw/web/some-article.md"
 *
 * This script:
 * 1. Finds raw notes for the topic (or a specific file)
 * 2. Reads existing wiki notes for dedup
 * 3. Outputs the LLM prompt to stdout (for piping to an LLM)
 *    OR invokes the LLM directly if --execute is passed
 * 4. Parses LLM output and writes wiki notes
 * 5. Updates raw note status to "compiled"
 * 6. Logs the compile event
 */

import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { parseFrontmatter, generateFrontmatter, formatIso8601Tz } from "../src/frontmatter.mjs";
import { generateDedupKey, findExistingByDedupKey } from "../src/dedup.mjs";
import { extractHumanOverrides, mergeWithOverrides } from "../src/human-override.mjs";
import { writeNote } from "../src/note-writer.mjs";
import { assertWithinBoundary } from "../src/boundary.mjs";

const args = process.argv.slice(2);
function getArg(name) {
  const idx = args.indexOf(`--${name}`);
  if (idx === -1 || idx + 1 >= args.length) return null;
  return args[idx + 1];
}
const hasFlag = (name) => args.includes(`--${name}`);

const topic = getArg("topic");
const file = getArg("file");
const dryRun = hasFlag("dry-run");
const batchSize = parseInt(getArg("batch-size") || "10", 10);

if (!topic && !file) {
  console.error("Usage: node scripts/compile-source.mjs --topic <topic> [--file <path>] [--dry-run] [--batch-size N]");
  process.exit(1);
}

const config = loadConfig();
const vaultPath = config.vaultPath;
const machineRoot = config.machineRoot;

// Step 1: Find raw notes
const rawNotes = findRawNotes(vaultPath, machineRoot, topic, file);
if (rawNotes.length === 0) {
  console.log("No queued raw notes found for the given topic/file.");
  process.exit(0);
}

console.log(`Found ${rawNotes.length} raw note(s) to compile.`);
if (rawNotes.length > batchSize) {
  console.log(`Batch size is ${batchSize} — processing first ${batchSize} only.`);
  rawNotes.length = batchSize;  // Truncate to batch size
}

// Step 2: Find existing wiki notes for dedup context
const existingWiki = findExistingWikiNotes(vaultPath, machineRoot, topic || extractTopic(rawNotes[0]));

// Step 3: Build LLM prompt
const promptTemplate = fs.readFileSync(
  path.join(config.projectRoot, "prompts", "compile-source.md"),
  "utf8"
);

for (const raw of rawNotes) {
  console.log(`\nCompiling: ${raw.relativePath}`);

  const rawContent = fs.readFileSync(raw.fullPath, "utf8");
  const rawFm = parseFrontmatter(rawContent);

  const prompt = promptTemplate
    .replace("{{RAW_CONTENT}}", rawContent)
    .replace("{{TOPIC}}", rawFm?.topic || topic || "")
    .replace("{{EXISTING_NOTES}}", formatExistingNotes(existingWiki));

  if (dryRun) {
    console.log("--- DRY RUN: LLM prompt would be ---");
    console.log(prompt.slice(0, 500) + "...");
    console.log("--- End dry run ---");
    continue;
  }

  // Output prompt for external LLM piping
  // In production, replace this with actual LLM call
  console.log("LLM_PROMPT_START");
  console.log(prompt);
  console.log("LLM_PROMPT_END");
  console.log("\nTo complete compilation, pipe LLM output to: node scripts/apply-compile-output.mjs");
}

// --- Helper functions ---

function findRawNotes(vaultPath, machineRoot, topic, specificFile) {
  if (specificFile) {
    const fullPath = path.join(vaultPath, specificFile);
    if (!fs.existsSync(fullPath)) {
      console.error(`File not found: ${specificFile}`);
      process.exit(1);
    }
    return [{ fullPath, relativePath: specificFile }];
  }

  const rawDir = path.join(vaultPath, machineRoot, "10-raw");
  if (!fs.existsSync(rawDir)) return [];

  const results = [];
  walkDir(rawDir, (filePath) => {
    if (!filePath.endsWith(".md")) return;
    const content = fs.readFileSync(filePath, "utf8");
    const fm = parseFrontmatter(content);
    if (fm && fm.kb_type === "raw" && fm.status === "queued") {
      if (!topic || (fm.topic && fm.topic.toLowerCase().includes(topic.toLowerCase()))) {
        results.push({
          fullPath: filePath,
          relativePath: path.relative(vaultPath, filePath).replace(/\\/g, "/")
        });
      }
    }
  });

  return results;
}

function findExistingWikiNotes(vaultPath, machineRoot, topic) {
  const wikiDir = path.join(vaultPath, machineRoot, "20-wiki");
  if (!fs.existsSync(wikiDir)) return [];

  const results = [];
  walkDir(wikiDir, (filePath) => {
    if (!filePath.endsWith(".md")) return;
    const content = fs.readFileSync(filePath, "utf8");
    const fm = parseFrontmatter(content);
    if (fm && fm.kb_type === "wiki") {
      if (!topic || (fm.topic && fm.topic.toLowerCase().includes(topic.toLowerCase()))) {
        results.push({
          fullPath: filePath,
          relativePath: path.relative(vaultPath, filePath).replace(/\\/g, "/"),
          frontmatter: fm,
          title: path.basename(filePath, ".md")
        });
      }
    }
  });

  return results;
}

function formatExistingNotes(notes) {
  if (notes.length === 0) return "(none)";
  return notes
    .map(n => `- ${n.title} (${n.frontmatter.wiki_kind}) [${n.relativePath}]`)
    .join("\n");
}

function extractTopic(raw) {
  const content = fs.readFileSync(raw.fullPath, "utf8");
  const fm = parseFrontmatter(content);
  return fm?.topic || "";
}

function walkDir(dir, callback) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkDir(full, callback);
    else callback(full);
  }
}
```

### Part C — Create `scripts/apply-compile-output.mjs`

This script takes LLM output (JSON array of note objects) and writes them to the Vault with dedup and human-override handling.

**Create** `obsidian-kb-local/scripts/apply-compile-output.mjs`:

```js
#!/usr/bin/env node

/**
 * Apply LLM compile output to the Vault.
 *
 * Reads JSON from stdin (array of wiki note objects from the LLM),
 * applies dedup check, human-override preservation, and writes to Vault.
 *
 * Usage:
 *   cat llm-output.json | node scripts/apply-compile-output.mjs --raw-path "08-AI知识库/10-raw/web/article.md"
 */

import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { generateFrontmatter, formatIso8601Tz, parseFrontmatter } from "../src/frontmatter.mjs";
import { generateDedupKey, findExistingByDedupKey } from "../src/dedup.mjs";
import { extractHumanOverrides, mergeWithOverrides } from "../src/human-override.mjs";
import { writeNote } from "../src/note-writer.mjs";

const args = process.argv.slice(2);
function getArg(name) {
  const idx = args.indexOf(`--${name}`);
  if (idx === -1 || idx + 1 >= args.length) return null;
  return args[idx + 1];
}

const rawPath = getArg("raw-path");
if (!rawPath) {
  console.error("Usage: cat llm-output.json | node scripts/apply-compile-output.mjs --raw-path <path>");
  process.exit(1);
}

// Read JSON from stdin
const chunks = [];
for await (const chunk of process.stdin) {
  chunks.push(chunk);
}
const input = Buffer.concat(chunks).toString("utf8");

let notes;
try {
  notes = JSON.parse(input);
  if (!Array.isArray(notes)) {
    throw new Error("Expected JSON array");
  }
} catch (e) {
  console.error(`Failed to parse LLM output as JSON: ${e.message}`);
  process.exit(1);
}

const config = loadConfig();
const now = formatIso8601Tz(new Date());
const today = now.slice(0, 10);
const logEntries = [];

const kindDirMap = {
  concept: "concepts",
  entity: "entities",
  source: "sources",
  synthesis: "syntheses"
};

for (const note of notes) {
  const { wiki_kind, title, topic, body, source_url } = note;

  const dir = kindDirMap[wiki_kind];
  if (!dir) {
    console.error(`Unknown wiki_kind: ${wiki_kind} — skipping`);
    continue;
  }

  const dedupKey = generateDedupKey(topic, wiki_kind, source_url || "");
  const safeName = title.replace(/[<>:"/\\|?*]/g, "").replace(/\s+/g, "-").slice(0, 100);

  // Check for existing note with same dedup key
  const existingPath = findExistingByDedupKey(config.vaultPath, config.machineRoot, dedupKey);

  let finalBody = body;
  let notePath;

  if (existingPath) {
    // Existing note found — merge with human-override preservation
    console.log(`  Updating existing: ${existingPath}`);
    notePath = existingPath;

    const existingContent = fs.readFileSync(path.join(config.vaultPath, existingPath), "utf8");
    const overrides = extractHumanOverrides(existingContent);
    finalBody = mergeWithOverrides(body, overrides);
  } else {
    // New note
    notePath = `${config.machineRoot}/20-wiki/${dir}/${safeName}.md`;
    console.log(`  Creating new: ${notePath}`);
  }

  const frontmatter = generateFrontmatter("wiki", {
    wiki_kind,
    topic,
    compiled_from: [rawPath],
    compiled_at: now,
    kb_date: today,
    review_state: "draft",
    kb_source_count: 1,
    dedup_key: dedupKey
  });

  const content = `${frontmatter}\n\n# ${title}\n\n${finalBody}\n`;

  writeNote(config, { path: notePath, content }, { allowFilesystemFallback: true });
  console.log(`  ✓ Written: ${notePath}`);

  logEntries.push({
    timestamp: now,
    action: existingPath ? "update" : "create",
    path: notePath,
    raw_source: rawPath,
    dedup_key: dedupKey
  });
}

// Update raw note status to "compiled"
const rawFullPath = path.join(config.vaultPath, rawPath);
if (fs.existsSync(rawFullPath)) {
  let rawContent = fs.readFileSync(rawFullPath, "utf8");
  rawContent = rawContent.replace(/status:\s*["']?queued["']?/, `status: "compiled"`);
  fs.writeFileSync(rawFullPath, rawContent, "utf8");
  console.log(`  ✓ Updated raw note status: ${rawPath} → compiled`);
}

// Write compile log (to companion repo, NOT Vault)
const logDir = path.join(config.projectRoot, "logs");
fs.mkdirSync(logDir, { recursive: true });
const logFile = path.join(logDir, `compile-${today}.jsonl`);
for (const entry of logEntries) {
  fs.appendFileSync(logFile, JSON.stringify(entry) + "\n", "utf8");
}
console.log(`\n✓ Compile log: ${logFile}`);
```

### Part D — Create `scripts/health-check.mjs`

**Create** `obsidian-kb-local/scripts/health-check.mjs`:

```js
#!/usr/bin/env node

/**
 * Run health check on the knowledge base.
 * Checks for orphans, stale notes, contract violations, dedup conflicts.
 *
 * Usage:
 *   node scripts/health-check.mjs
 *   node scripts/health-check.mjs --json  (machine-readable output)
 */

import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { parseFrontmatter, validateRawFrontmatter, validateWikiFrontmatter } from "../src/frontmatter.mjs";

const config = loadConfig();
const vaultPath = config.vaultPath;
const machineRoot = config.machineRoot;
const jsonOutput = process.argv.includes("--json");

const report = {
  orphan_wiki: [],
  stale_wiki: [],
  missing_source: [],
  contract_violations: [],
  dedup_conflicts: []
};

// Scan all notes
const rawNotes = scanNotes(path.join(vaultPath, machineRoot, "10-raw"));
const wikiNotes = scanNotes(path.join(vaultPath, machineRoot, "20-wiki"));

// Check contract violations
for (const note of rawNotes) {
  try {
    validateRawFrontmatter(note.frontmatter);
  } catch (e) {
    report.contract_violations.push({
      path: note.relativePath,
      issue: e.message,
      severity: "warning"
    });
  }
}

for (const note of wikiNotes) {
  try {
    validateWikiFrontmatter(note.frontmatter);
  } catch (e) {
    report.contract_violations.push({
      path: note.relativePath,
      issue: e.message,
      severity: "warning"
    });
  }
}

// Check orphan wiki (no compiled_from match)
for (const wiki of wikiNotes) {
  const fm = wiki.frontmatter;
  if (fm && Array.isArray(fm.compiled_from) && fm.compiled_from.length > 0) {
    for (const src of fm.compiled_from) {
      const srcPath = path.join(vaultPath, src);
      if (!fs.existsSync(srcPath)) {
        report.missing_source.push({
          wiki_path: wiki.relativePath,
          missing_raw: src,
          severity: "critical"
        });
      }
    }
  } else if (fm && fm.kb_type === "wiki" && fm.wiki_kind !== "synthesis") {
    report.orphan_wiki.push({
      path: wiki.relativePath,
      severity: "warning"
    });
  }
}

// Check dedup conflicts
const dedupMap = new Map();
for (const wiki of wikiNotes) {
  const key = wiki.frontmatter?.dedup_key;
  if (key && typeof key === "string" && key.length > 0) {
    if (dedupMap.has(key)) {
      report.dedup_conflicts.push({
        dedup_key: key,
        files: [dedupMap.get(key), wiki.relativePath],
        severity: "critical"
      });
    } else {
      dedupMap.set(key, wiki.relativePath);
    }
  }
}

// Output
if (jsonOutput) {
  console.log(JSON.stringify(report, null, 2));
} else {
  const total = Object.values(report).reduce((sum, arr) => sum + arr.length, 0);
  console.log(`\n=== KB Health Check ===\n`);
  console.log(`Raw notes:  ${rawNotes.length}`);
  console.log(`Wiki notes: ${wikiNotes.length}`);
  console.log(`Issues:     ${total}\n`);

  for (const [category, items] of Object.entries(report)) {
    if (items.length > 0) {
      console.log(`## ${category} (${items.length})`);
      for (const item of items) {
        console.log(`  - [${item.severity}] ${item.path || item.wiki_path || item.dedup_key}: ${item.issue || item.missing_raw || ""}`);
      }
      console.log();
    }
  }

  if (total === 0) {
    console.log("✓ All checks passed.");
  }
}

// --- Helpers ---

function scanNotes(dir) {
  if (!fs.existsSync(dir)) return [];
  const results = [];
  walkDir(dir, (filePath) => {
    if (!filePath.endsWith(".md")) return;
    const content = fs.readFileSync(filePath, "utf8");
    const fm = parseFrontmatter(content);
    results.push({
      fullPath: filePath,
      relativePath: path.relative(vaultPath, filePath).replace(/\\/g, "/"),
      frontmatter: fm || {}
    });
  });
  return results;
}

function walkDir(dir, callback) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkDir(full, callback);
    else callback(full);
  }
}
```

### Part E — Add npm scripts

**Modify** `obsidian-kb-local/package.json` — add to `"scripts"`:
```json
"compile-source": "node scripts/compile-source.mjs",
"apply-compile": "node scripts/apply-compile-output.mjs",
"health-check": "node scripts/health-check.mjs"
```

### Part F — Create logs directory

**Create** `obsidian-kb-local/logs/.gitkeep` (empty file to track the logs directory in git).

## Acceptance Criteria

1. Three prompt templates created in `prompts/` directory
2. `compile-source.mjs --topic X --dry-run` runs without error, outputs prompt preview
3. `apply-compile-output.mjs` reads JSON from stdin, writes wiki notes with dedup + human-override
4. `health-check.mjs` runs and reports on KB state
5. Compile logs written to `obsidian-kb-local/logs/` (NOT to Vault)
6. Raw note `status` updated from `queued` to `compiled` after successful compile
7. Existing wiki notes with matching dedup key are updated in-place, not duplicated
8. `<!-- human-override -->` blocks in existing wiki notes survive recompilation
9. All existing tests pass

## Safety Constraints

- All writes go through `writeNote()` with `assertWithinBoundary()` guard
- Compile batch size capped at 10 notes per run (OneDrive sync safety)
- Logs written to companion repo only — NEVER to Vault `90-ops/logs/`
- LLM timeout: 120 seconds per source (configurable)
- On LLM failure: mark raw note `status: error`, continue with next note
- Do NOT install new npm dependencies
