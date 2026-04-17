# Baseline Audit - 2026-04-04

## Files Targeted In Safety Lockdown

| File | Planned change | Reason |
| --- | --- | --- |
| `D:\OneDrive - zn\文档\Obsidian Vault\second_brain_script.js` | Add `08-AI知识库` to `skipFolders` | Prevent legacy organizer from mutating KB notes |
| `D:\OneDrive - zn\文档\Obsidian Vault\.obsidian\plugins\quickadd\data.json` | Set `runOnStartup` to `false` | Stop startup macro from auto-running on vault open |
| `D:\OneDrive - zn\文档\Obsidian Vault\.obsidian\plugins\templater-obsidian\data.json` | Clear root folder template | Prevent stale root template injection |
| `obsidian-kb-local/src/note-writer.mjs` | Add `assertWithinBoundary()` guard | Prevent CLI fallback writes outside `08-AI知识库` |

## Pre-existing State

- `second_brain_script.js` scans all markdown files unless a folder is explicitly skipped.
- QuickAdd has a single `第二大脑` macro with `runOnStartup: true`.
- Templater root folder template points `/` to `second_brain.md`.
- `note-writer.mjs` previously allowed filesystem fallback writes without boundary validation.

## Validation Checklist

- [x] `second_brain_script.js` skips `08-AI知识库`
- [x] QuickAdd startup macro is disabled
- [x] Templater root template is cleared
- [x] `assertWithinBoundary()` rejects out-of-bound paths
- [x] `writeNote()` checks the boundary before CLI or filesystem I/O
- [ ] `cmd /c npm run doctor` confirms CLI registration
- [x] `node --test tests/boundary.test.mjs` passes
- [x] `cmd /c npm test` passes

## Current Blocker

- As of 2026-04-04, the desktop app exists on disk, but the Obsidian CLI is still not registered in the shell.
- `cmd /c where obsidian` and `cmd /c where Obsidian.com` both return no result.
- Backups for the three live Vault files are stored in `obsidian-kb-local/docs/vault-snapshots/2026-04-04-unit0/`.
