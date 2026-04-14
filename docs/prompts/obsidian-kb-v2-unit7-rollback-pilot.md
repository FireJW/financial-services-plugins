# Codex Prompt — Unit 7: Rollback Script and Pilot

> **Depends on**: All previous units (0-6) should be complete.

## Context

You are working in the `obsidian-kb-local` companion repo at:
```
C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins\obsidian-kb-local\
```

The Vault is at `D:\OneDrive - zn\文档\Obsidian Vault`, config.machineRoot = `08-AI知识库`.

This is the final unit. It creates a rollback script for safely removing machine-generated content and defines the pilot testing procedure.

## Task

### Part A — Create `scripts/rollback.mjs`

**Create** `obsidian-kb-local/scripts/rollback.mjs`:

```js
#!/usr/bin/env node

/**
 * Rollback machine-generated content from the knowledge base.
 *
 * Usage:
 *   node scripts/rollback.mjs --dry-run          List files that would be deleted
 *   node scripts/rollback.mjs --execute           Delete machine-generated files
 *   node scripts/rollback.mjs --execute --topic X  Only rollback files for a specific topic
 *
 * Safety rules:
 * - ONLY deletes files where managed_by: codex
 * - NEVER touches files where managed_by: human
 * - NEVER touches files outside 08-AI知识库
 * - NEVER deletes README.md, KB Home.md, or contract files
 * - Generates a rollback log before executing
 */

import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import { parseFrontmatter } from "../src/frontmatter.mjs";
import { assertWithinBoundary } from "../src/boundary.mjs";

const args = process.argv.slice(2);
function getArg(name) {
  const idx = args.indexOf(`--${name}`);
  if (idx === -1 || idx + 1 >= args.length) return null;
  return args[idx + 1];
}
const hasFlag = (name) => args.includes(`--${name}`);

const dryRun = hasFlag("dry-run");
const execute = hasFlag("execute");
const topic = getArg("topic");

if (!dryRun && !execute) {
  console.error("Usage:");
  console.error("  node scripts/rollback.mjs --dry-run           Preview what would be deleted");
  console.error("  node scripts/rollback.mjs --execute            Delete machine-generated files");
  console.error("  node scripts/rollback.mjs --execute --topic X  Rollback specific topic only");
  process.exit(1);
}

const config = loadConfig();
const vaultPath = config.vaultPath;
const machineRoot = config.machineRoot;
const kbRoot = path.join(vaultPath, machineRoot);

// Protected files that should never be deleted
const PROTECTED_PATTERNS = [
  /README\.md$/i,
  /KB Home\.md$/i,
  /contracts\//,
  /manifests\//,
  /migration\//,
  /Runbooks\//,
  /\.gitkeep$/
];

function isProtected(relativePath) {
  return PROTECTED_PATTERNS.some(pattern => pattern.test(relativePath));
}

// Scan for machine-generated files
const candidates = [];
walkDir(kbRoot, (filePath) => {
  if (!filePath.endsWith(".md")) return;

  const relativePath = path.relative(vaultPath, filePath).replace(/\\/g, "/");

  // Boundary check — should always pass but defense in depth
  try {
    assertWithinBoundary(relativePath, machineRoot);
  } catch {
    return; // Skip files outside boundary (shouldn't happen)
  }

  if (isProtected(relativePath)) return;

  const content = fs.readFileSync(filePath, "utf8");
  const fm = parseFrontmatter(content);

  if (!fm) return;
  if (fm.managed_by !== "codex") return;

  // Topic filter
  if (topic && fm.topic && !fm.topic.toLowerCase().includes(topic.toLowerCase())) {
    return;
  }

  candidates.push({
    path: filePath,
    relativePath,
    kb_type: fm.kb_type,
    topic: fm.topic,
    wiki_kind: fm.wiki_kind,
    managed_by: fm.managed_by
  });
});

console.log(`\n=== Rollback ${dryRun ? "(DRY RUN)" : "(EXECUTE)"} ===\n`);
console.log(`KB root: ${kbRoot}`);
console.log(`Topic filter: ${topic || "(all)"}`);
console.log(`Candidates: ${candidates.length} machine-generated files\n`);

if (candidates.length === 0) {
  console.log("No machine-generated files found. Nothing to rollback.");
  process.exit(0);
}

// List candidates
for (const c of candidates) {
  const label = `[${c.kb_type}/${c.wiki_kind || c.managed_by}] ${c.relativePath}`;
  if (dryRun) {
    console.log(`  WOULD DELETE: ${label}`);
  } else {
    console.log(`  DELETING: ${label}`);
  }
}

if (dryRun) {
  console.log(`\n→ ${candidates.length} file(s) would be deleted.`);
  console.log("→ Run with --execute to perform the deletion.");
  process.exit(0);
}

// Execute: write rollback log first, then delete
const logDir = path.join(config.projectRoot, "logs");
fs.mkdirSync(logDir, { recursive: true });

const now = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const logFile = path.join(logDir, `rollback-${now}.json`);

const logData = {
  timestamp: new Date().toISOString(),
  topic_filter: topic || null,
  files_deleted: candidates.map(c => ({
    path: c.relativePath,
    kb_type: c.kb_type,
    topic: c.topic
  }))
};

fs.writeFileSync(logFile, JSON.stringify(logData, null, 2), "utf8");
console.log(`\n✓ Rollback log saved: ${logFile}`);

// Delete files
let deleted = 0;
for (const c of candidates) {
  try {
    fs.unlinkSync(c.path);
    deleted++;
  } catch (e) {
    console.error(`  ✗ Failed to delete ${c.relativePath}: ${e.message}`);
  }
}

// Clean up empty directories (bottom-up)
cleanEmptyDirs(kbRoot);

console.log(`\n✓ Deleted ${deleted}/${candidates.length} files.`);

// --- Helpers ---

function walkDir(dir, callback) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkDir(full, callback);
    else callback(full);
  }
}

function cleanEmptyDirs(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      const full = path.join(dir, entry.name);
      cleanEmptyDirs(full);
      // Remove if empty after recursive clean
      try {
        const remaining = fs.readdirSync(full);
        if (remaining.length === 0) {
          fs.rmdirSync(full);
        }
      } catch { /* ignore */ }
    }
  }
}
```

### Part B — Add npm script

**Modify** `obsidian-kb-local/package.json` — add to `"scripts"`:
```json
"rollback": "node scripts/rollback.mjs"
```

### Part C — Create pilot checklist

**Create** `obsidian-kb-local/docs/pilot-checklist.md`:

```markdown
# Pilot Checklist

## Prerequisites

- [ ] Unit 0: Safety lockdown complete
  - [ ] `second_brain_script.js` has `08-AI知识库` in skipFolders
  - [ ] QuickAdd `runOnStartup: false`
  - [ ] Templater root template cleared
  - [ ] `boundary.test.mjs` passes
- [ ] Unit 1: Frontmatter enforcement tests pass
- [ ] Unit 2: Dedup + human-override tests pass
- [ ] Unit 3: Bootstrap namespace created in Vault
- [ ] Unit 4: Ingestion script works
- [ ] Unit 5: Compile pipeline scripts created
- [ ] Unit 6: Dashboard views created

## Pilot Procedure (1-3 topics)

### 1. Ingest raw note

```powershell
echo "Test content about LLM agents" | cmd /c "cd obsidian-kb-local && node scripts/ingest-web.mjs --topic \"LLM Agents\" --url \"https://example.com\" --title \"Test Article\""
```

Verify:
- [ ] Note created in `08-AI知识库/10-raw/web/`
- [ ] Frontmatter has all v2 fields
- [ ] `status: queued`

### 2. Compile to wiki

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"LLM Agents\" --dry-run"
```

Review the LLM prompt output, then compile:

```powershell
# Pipe LLM output to apply script:
echo '[{"wiki_kind":"source","title":"LLM Agents Overview","topic":"LLM Agents","body":"Test wiki content.","source_url":"https://example.com"}]' | cmd /c "cd obsidian-kb-local && node scripts/apply-compile-output.mjs --raw-path \"08-AI知识库/10-raw/web/Test-Article.md\""
```

Verify:
- [ ] Wiki note created in `08-AI知识库/20-wiki/sources/`
- [ ] Wiki note has `dedup_key`, `compiled_from`, `kb_source_count`
- [ ] Raw note status changed to `compiled`
- [ ] Compile log written to `obsidian-kb-local/logs/`

### 3. Verify dashboard

Open Obsidian and navigate to `08-AI知识库/30-views/00-KB Dashboard.md`:
- [ ] Recent Raw table shows the ingested note
- [ ] Recent Wiki table shows the compiled note
- [ ] Stale Notes view works (may be empty)
- [ ] Sources by Topic groups correctly

### 4. Test recompile (dedup + human-override)

Add a `<!-- human-override -->` block to the wiki note manually, then recompile:
- [ ] Override block survives recompilation
- [ ] No duplicate wiki note created
- [ ] `compiled_at` and `kb_source_count` updated

### 5. Run health check

```powershell
cmd /c "cd obsidian-kb-local && node scripts/health-check.mjs"
```

- [ ] No critical issues reported
- [ ] Contract violations identified (if any)

### 6. Rollback drill

```powershell
cmd /c "cd obsidian-kb-local && node scripts/rollback.mjs --dry-run"
cmd /c "cd obsidian-kb-local && node scripts/rollback.mjs --execute"
```

- [ ] Dry run lists machine-generated files only
- [ ] Execute deletes only `managed_by: codex` files
- [ ] Human-managed files untouched
- [ ] Rollback log saved in `obsidian-kb-local/logs/`

## Success Criteria

- S1. `08-AI知识库` established; zero writes to `00-07` directories
- S2. Web clip → raw → compile → wiki view in under 5 minutes
- S3. All wiki notes have `compiled_from`, `compiled_at`, `managed_by`
- S4. `health-check` detects contract violations, orphans, stale notes
- S5. At least one pilot topic can be stably recompiled without duplicates
```

## Acceptance Criteria

1. `rollback.mjs --dry-run` lists machine-generated files without deleting
2. `rollback.mjs --execute` deletes ONLY `managed_by: codex` files
3. Protected files (README.md, KB Home.md, contracts, manifests, migration) are never deleted
4. Topic filter `--topic X` restricts rollback to matching notes
5. Rollback log saved to `obsidian-kb-local/logs/` before any deletion
6. Empty directories cleaned up after rollback
7. Pilot checklist covers the complete raw→compile→wiki→dashboard→rollback chain
8. All existing tests pass

## Safety Constraints

- NEVER delete files outside `08-AI知识库/`
- NEVER delete files where `managed_by: human`
- ALWAYS write rollback log BEFORE executing deletions
- ALWAYS use `assertWithinBoundary()` as defense-in-depth
- Do NOT install new npm dependencies
- Rollback cannot be undone — rollback log serves as the only recovery record
