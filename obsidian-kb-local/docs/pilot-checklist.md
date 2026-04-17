# Pilot Checklist

## Prerequisites

- [ ] Unit 0: Safety lockdown complete
  - [ ] `second_brain_script.js` includes `08-AI知识库` in the skip list
  - [ ] QuickAdd `runOnStartup` is `false`
  - [ ] Templater root template is cleared
  - [ ] `boundary.test.mjs` passes
- [ ] Unit 1: Frontmatter enforcement tests pass
- [ ] Unit 2: Dedup and human-override tests pass
- [ ] Unit 3: Bootstrap namespace created in the vault
- [ ] Unit 4: Ingestion script works
- [ ] Unit 5: Compile pipeline scripts exist and pass smoke tests
- [ ] Unit 6: Dashboard view notes exist

## Pilot Procedure

### 1. Ingest raw note

```powershell
echo "Test content about LLM agents" | cmd /c "cd obsidian-kb-local && node scripts/ingest-web.mjs --topic \"LLM Agents\" --url \"https://example.com\" --title \"Test Article\""
```

Verify:

- [ ] Note created under `08-AI知识库/10-raw/web/`
- [ ] Frontmatter includes all v2 raw fields
- [ ] `status: queued`

### 2. Compile to wiki

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"LLM Agents\" --dry-run"
```

Review the prompt output, then apply a compile result:

```powershell
echo "[{\"wiki_kind\":\"source\",\"title\":\"LLM Agents Overview\",\"topic\":\"LLM Agents\",\"body\":\"Test wiki content.\",\"source_url\":\"https://example.com\"}]" | cmd /c "cd obsidian-kb-local && node scripts/apply-compile-output.mjs --raw-path \"08-AI知识库/10-raw/web/Test-Article.md\""
```

Verify:

- [ ] Wiki note created under `08-AI知识库/20-wiki/sources/`
- [ ] Wiki note includes `dedup_key`, `compiled_from`, and `kb_source_count`
- [ ] Raw note status changed to `compiled`
- [ ] Compile log written to `obsidian-kb-local/logs/`

### 3. Verify dashboard

Open Obsidian and inspect:

- [ ] `08-AI知识库/30-views/00-KB Dashboard.md`
- [ ] `08-AI知识库/30-views/01-Stale Notes.md`
- [ ] `08-AI知识库/30-views/02-Open Questions.md`
- [ ] `08-AI知识库/30-views/03-Sources by Topic.md`

Confirm:

- [ ] Recent Raw shows the ingested note
- [ ] Recent Wiki shows the compiled note
- [ ] Stale Notes renders correctly
- [ ] Sources by Topic groups content by topic

### 4. Recompile test

Add a `<!-- human-override -->` block to a wiki note manually, then reapply compile output.

Verify:

- [ ] Override block survives recompilation
- [ ] No duplicate wiki note is created
- [ ] `compiled_at` and `kb_source_count` update correctly

### 5. Run health check

```powershell
cmd /c "cd obsidian-kb-local && node scripts/health-check.mjs"
```

- [ ] No unexpected critical issues
- [ ] Contract violations are readable and actionable when present

### 6. Rollback drill

```powershell
cmd /c "cd obsidian-kb-local && node scripts/rollback.mjs --dry-run"
cmd /c "cd obsidian-kb-local && node scripts/rollback.mjs --execute"
```

Verify:

- [ ] Dry run lists only `managed_by: codex` notes
- [ ] Execute deletes only machine-generated notes
- [ ] Human-managed notes remain untouched
- [ ] Rollback log is written before deletion

## Success Criteria

- [ ] `08-AI知识库` is the only machine-write namespace
- [ ] Raw -> compile -> wiki works in under 5 minutes for a pilot topic
- [ ] Wiki notes consistently include `compiled_from`, `compiled_at`, and `managed_by`
- [ ] `health-check` surfaces stale notes, missing sources, and dedup conflicts
- [ ] At least one pilot topic can be recompiled without duplicates

## Provider Sync Notes

- [ ] `cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"LLM Agents\" --execute"` succeeds with the active `.codex/config.toml`
- [ ] `cmd /c npm run doctor` reports `Codex LLM provider ready`
- [ ] changing `.codex/config.toml` via `ccswitch` is reflected on the next compile run without editing this project
- [ ] failed provider calls mark the raw note as `error` and write `logs/compile-errors-YYYY-MM-DD.jsonl`
