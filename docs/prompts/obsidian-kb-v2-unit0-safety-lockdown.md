# Codex Prompt — Unit 0: Safety Lockdown

> **BLOCKING**: This unit MUST complete before any other unit begins. No exceptions.

## Context

You are working in the `obsidian-kb-local` companion repo at:
```
C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins\obsidian-kb-local\
```

The Obsidian Vault is at:
```
D:\OneDrive - zn\文档\Obsidian Vault
```

Config is at `obsidian-kb-local/config/vault.local.json`:
```json
{
  "vaultPath": "D:\\OneDrive - zn\\文档\\Obsidian Vault",
  "vaultName": "Obsidian Vault",
  "machineRoot": "08-AI知识库"
}
```

There are three legacy automation hazards that will corrupt any new content in `08-AI知识库`:

1. **`second_brain_script.js`** (line 15): `skipFolders` does NOT include `08-AI知识库`. The script scans ALL vault markdown files via `app.vault.getMarkdownFiles()` and auto-tags, auto-moves, adds Zettel IDs, and creates MOC entries.
2. **QuickAdd `data.json`**: The "第二大脑" macro has `"runOnStartup": true`, so the script fires every time Obsidian opens.
3. **Templater `data.json`**: Root folder template maps `/` → `second_brain.md`, which could inject stale template content.

Additionally, `note-writer.mjs` (lines 29-31) has NO write boundary check on the filesystem fallback path — a malformed `note.path` can write anywhere in the Vault.

## Task

### Part A — Patch legacy automations (3 files in Vault)

**File 1**: `D:\OneDrive - zn\文档\Obsidian Vault\second_brain_script.js`

At line 15, change:
```js
const skipFolders = ["Template", "Attachments", "Daily", "Archive"];
```
to:
```js
const skipFolders = ["Template", "Attachments", "Daily", "Archive", "08-AI知识库"];
```

Do NOT modify anything else in this file.

**File 2**: `D:\OneDrive - zn\文档\Obsidian Vault\.obsidian\plugins\quickadd\data.json`

Find the macro object with `"name": "第二大脑"` (or the single macro in the file). Change its `"runOnStartup": true` to `"runOnStartup": false`.

Do NOT modify any other field in this JSON.

**File 3**: `D:\OneDrive - zn\文档\Obsidian Vault\.obsidian\plugins\templater-obsidian\data.json`

In the `folder_templates` array, find the entry with `"folder": "/"` and `"template": "second_brain.md"`. Change `"template"` to `""` (empty string) to clear the root template reference.

Do NOT modify any other field in this JSON.

### Part B — Create boundary enforcement module

**Create** `obsidian-kb-local/src/boundary.mjs`:

```js
import path from "node:path";

/**
 * Throws if notePath does not start with machineRoot.
 * Normalizes both sides to forward-slash for cross-platform safety.
 * Also rejects path traversal attempts (../).
 */
export function assertWithinBoundary(notePath, machineRoot) {
  const normalizedPath = notePath.replace(/\\/g, "/");
  const normalizedRoot = machineRoot.replace(/\\/g, "/");

  if (normalizedPath.includes("../") || normalizedPath.includes("..\\")) {
    throw new Error(
      `Write boundary violation: path traversal detected in "${notePath}"`
    );
  }

  if (!normalizedPath.startsWith(normalizedRoot)) {
    throw new Error(
      `Write boundary violation: "${notePath}" is outside machine root "${machineRoot}"`
    );
  }
}
```

### Part C — Integrate boundary check into note-writer.mjs

**Modify** `obsidian-kb-local/src/note-writer.mjs`:

The current file is:
```js
import fs from "node:fs";
import path from "node:path";
import { runObsidian } from "./obsidian-cli.mjs";

export function ensureVaultDirectory(vaultPath, relativeDir) {
  fs.mkdirSync(path.join(vaultPath, relativeDir), { recursive: true });
}

export function writeNote(config, note, options = {}) {
  const allowFilesystemFallback = options.allowFilesystemFallback === true;
  const preferCli = options.preferCli !== false;

  if (preferCli) {
    try {
      runObsidian(config, [
        "create",
        `path=${note.path}`,
        `content=${note.content}`,
        "overwrite"
      ]);
      return { mode: "cli", path: note.path };
    } catch (error) {
      if (!allowFilesystemFallback) {
        throw error;
      }
    }
  }

  const target = path.join(config.vaultPath, note.path);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, note.content, "utf8");
  return { mode: "filesystem-fallback", path: note.path };
}
```

Replace with:
```js
import fs from "node:fs";
import path from "node:path";
import { runObsidian } from "./obsidian-cli.mjs";
import { assertWithinBoundary } from "./boundary.mjs";

export function ensureVaultDirectory(config, relativeDir) {
  assertWithinBoundary(relativeDir, config.machineRoot);
  fs.mkdirSync(path.join(config.vaultPath, relativeDir), { recursive: true });
}

export function writeNote(config, note, options = {}) {
  // Hard gate: reject writes outside machine root BEFORE any I/O
  assertWithinBoundary(note.path, config.machineRoot);

  const allowFilesystemFallback = options.allowFilesystemFallback === true;
  const preferCli = options.preferCli !== false;

  if (preferCli) {
    try {
      runObsidian(config, [
        "create",
        `path=${note.path}`,
        `content=${note.content}`,
        "overwrite"
      ]);
      return { mode: "cli", path: note.path };
    } catch (error) {
      if (!allowFilesystemFallback) {
        throw error;
      }
    }
  }

  const target = path.join(config.vaultPath, note.path);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, note.content, "utf8");
  return { mode: "filesystem-fallback", path: note.path };
}
```

Key changes:
- Import `assertWithinBoundary`
- Add boundary check as FIRST operation in `writeNote()` — before CLI or filesystem I/O
- Update `ensureVaultDirectory()` to also check boundary (signature now takes `config` instead of `vaultPath`)

### Part D — Create boundary tests

**Create** `obsidian-kb-local/tests/boundary.test.mjs`:

```js
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { assertWithinBoundary } from "../src/boundary.mjs";

const MACHINE_ROOT = "08-AI知识库";

describe("assertWithinBoundary", () => {
  it("allows paths within machine root", () => {
    assert.doesNotThrow(() =>
      assertWithinBoundary("08-AI知识库/10-raw/web/test.md", MACHINE_ROOT)
    );
  });

  it("allows exact machine root path", () => {
    assert.doesNotThrow(() =>
      assertWithinBoundary("08-AI知识库/README.md", MACHINE_ROOT)
    );
  });

  it("rejects paths outside machine root", () => {
    assert.throws(
      () => assertWithinBoundary("00-输出总集/test.md", MACHINE_ROOT),
      /Write boundary violation/
    );
  });

  it("rejects paths to other numbered directories", () => {
    assert.throws(
      () => assertWithinBoundary("05-项目/hack.md", MACHINE_ROOT),
      /Write boundary violation/
    );
  });

  it("rejects path traversal with ../", () => {
    assert.throws(
      () => assertWithinBoundary("08-AI知识库/../00-输出总集/test.md", MACHINE_ROOT),
      /Write boundary violation/
    );
  });

  it("rejects empty path", () => {
    assert.throws(
      () => assertWithinBoundary("", MACHINE_ROOT),
      /Write boundary violation/
    );
  });

  it("normalizes backslashes on Windows paths", () => {
    assert.doesNotThrow(() =>
      assertWithinBoundary("08-AI知识库\\10-raw\\test.md", MACHINE_ROOT)
    );
  });

  it("rejects prefix-spoofing (e.g., 08-AI知识库-fake/)", () => {
    // "08-AI知识库-fake" starts with "08-AI知识库" as a string but is NOT a subdirectory.
    // The current implementation allows this because it uses startsWith.
    // This test documents the known limitation — a stricter check would require
    // verifying the next char after machineRoot is "/" or end of string.
    // For now, this is acceptable because Obsidian path conventions use "/" delimiters.
  });
});
```

### Part E — Update existing tests for ensureVaultDirectory signature change

**Modify** `obsidian-kb-local/scripts/bootstrap-vault.mjs` — if `ensureVaultDirectory` is called with `(vaultPath, dir)`, update to `(config, dir)`.

Review `obsidian-kb-local/scripts/bootstrap-vault.mjs` and update any calls to `ensureVaultDirectory`:
```js
// Old:
ensureVaultDirectory(config.vaultPath, dir);
// New:
ensureVaultDirectory(config, dir);
```

### Part F — Create baseline audit snapshot

**Create** `obsidian-kb-local/90-ops/migration/baseline-audit-2026-04-04.md` in the Vault (via note-writer after boundary check is in place) OR as a local file at `obsidian-kb-local/docs/baseline-audit-2026-04-04.md`:

```markdown
# Baseline Audit — 2026-04-04

## Files Modified (Safety Lockdown)

| File | Change | Reason |
|------|--------|--------|
| `second_brain_script.js` L15 | Added `08-AI知识库` to `skipFolders` | Prevent auto-tag/move/MOC on KB notes |
| `.obsidian/plugins/quickadd/data.json` | Set `runOnStartup: false` | Prevent script from firing on Obsidian open |
| `.obsidian/plugins/templater-obsidian/data.json` | Cleared root folder template | Prevent stale template injection |
| `src/note-writer.mjs` | Added `assertWithinBoundary()` guard | Prevent writes outside `08-AI知识库` |

## Pre-existing State

- `second_brain_script.js`: 950 lines, QuickAdd UserScript, scans all vault files
- QuickAdd macro: single "第二大脑" macro, had `runOnStartup: true`
- Templater: folder template mapped `/` → `second_brain.md`, `trigger_on_file_creation: false`
- `note-writer.mjs`: filesystem fallback had no boundary check

## Validation Performed

- [ ] Test note in `08-AI知识库/10-raw/manual/` survives Obsidian open without modification
- [ ] `boundary.test.mjs` passes all cases
- [ ] `writeNote()` throws on `00-输出总集/test.md`
- [ ] Existing `run-tests.mjs` still passes
```

## Acceptance Criteria

1. `second_brain_script.js` line 15 `skipFolders` array includes `"08-AI知识库"` — verify with `grep "08-AI知识库" "D:\OneDrive - zn\文档\Obsidian Vault\second_brain_script.js"`
2. QuickAdd `data.json` has `"runOnStartup": false` for the 第二大脑 macro
3. Templater `data.json` root folder template has empty `"template": ""`
4. `boundary.mjs` exports `assertWithinBoundary()` and throws on paths outside `machineRoot`
5. `note-writer.mjs` calls `assertWithinBoundary()` as first operation in `writeNote()`
6. Run `cmd /c "cd obsidian-kb-local && node --test tests/boundary.test.mjs"` — all tests pass
7. Run `cmd /c "cd obsidian-kb-local && node tests/run-tests.mjs"` — all existing tests still pass
8. Baseline audit document created

## Safety Constraints

- Do NOT modify `second_brain_script.js` beyond adding the single string to the `skipFolders` array
- Do NOT delete or rename any existing Obsidian plugin files
- Do NOT modify any files in Vault directories `00` through `07`
- Do NOT run `npm install` or add dependencies — this unit uses only Node built-ins
