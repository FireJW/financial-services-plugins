# Workspace Safety

## Why This Exists

This repository has recently been recovered from a destructive workspace loss.
The biggest structural risk was not only one bad command. The bigger risk was
that the canonical working copy lived under:

- `.gemini/antigravity/scratch/`

That path behaves like an agent scratchpad, not a durable primary home for a
long-lived repository.

## Hard Rule

Do not treat the current scratch path as the canonical development home.

Use scratch only for:

- temporary recovery work
- disposable agent experiments
- short-lived validation copies

Keep the canonical working copy in a stable location such as:

- `C:\Users\<you>\dev\financial-services-plugins`
- `D:\Users\rickylu\dev\financial-services-plugins`
- WSL Linux filesystem, for example:
  - `/home/<you>/dev/financial-services-plugins`

If using WSL, prefer the Linux filesystem inside the distro rather than
developing under `/mnt/c/...`.

Important boundary:

- the repository's canonical code location can move to D drive
- the user's active Codex home/config can stay on C drive
- do not modify `C:\Users\rickylu\.codex\config.toml` or
  `C:\Users\rickylu\.codex\.codex-global-state.json` unless the user explicitly
  asks for a Codex config migration
- do not modify or clean `D:\Users\rickylu\repo-safety-backups\financial-services-plugins\`
  during normal development; treat it as a read-only recovery inventory

## Safety Workflow

### 1. Check the current workspace risk

```powershell
.\scripts\check-workspace-safety.ps1
```

This reports:

- current repository path
- risk level
- why the path is risky
- recommended stable target paths

### 2. Create a snapshot outside the workspace before file mutation

```powershell
.\scripts\repo-snapshot.ps1 -BackupRoot "D:\Users\rickylu\repo-safety-backups\financial-services-plugins" -MirrorLatest -IncludeGit
```

Defaults:

- creates a timestamped snapshot outside the repo under the user profile
- writes a manifest file
- does not include `.git` unless explicitly requested

Operational rule:

- for any delete, cleanup, move, rename, rollback, codemod, or batch rewrite,
  always add `-IncludeGit`, use a stable `-BackupRoot`, and capture the
  resulting manifest before continuing
- treat the backup root and mirrored snapshot output as read-only for the rest
  of the task

Useful variants:

```powershell
.\scripts\repo-snapshot.ps1 -MirrorLatest
.\scripts\repo-snapshot.ps1 -IncludeGit -MirrorLatest
.\scripts\repo-snapshot.ps1 -ZipSnapshot
.\scripts\repo-snapshot.ps1 -ExcludeTmp
```

Recommended default for active local work:

- keep `.tmp` included, because this repo uses local runtime artifacts and they
  may contain valuable recovery state

### 3. Dry-run every file-affecting command first

Before any real write, delete, move, or cleanup step:

- run the script's preview mode such as `--dry-run` or `-WhatIf`
- surface the exact candidate file list that will be changed
- stop if the candidate list is broader than intended
- if no preview mode exists, build an equivalent candidate report first and do
  not execute the real step until that report has been reviewed

Examples:

```powershell
.\scripts\prepare-safe-workspace.ps1 -TargetRoot "D:\Users\rickylu\dev"
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\repo-snapshot.ps1 -BackupRoot "D:\Users\rickylu\repo-safety-backups\financial-services-plugins" -MirrorLatest -IncludeGit -WhatIf
node scripts/rollback.mjs --dry-run
```

### 4. Prepare a stable canonical workspace

Dry run:

```powershell
.\scripts\prepare-safe-workspace.ps1 -TargetRoot "D:\Users\rickylu\dev"
```

Execute:

```powershell
.\scripts\prepare-safe-workspace.ps1 -TargetRoot "D:\Users\rickylu\dev" -IncludeGit -IncludeTmp -Execute
```

Use `-IncludeTmp` when the temporary outputs themselves are valuable ongoing
work product, not just disposable runtime noise.

## Recommended Operating Model

### Best practical Windows model

1. keep one stable canonical repo under `D:\Users\rickylu\dev\financial-services-plugins`
2. take git-inclusive snapshots before risky recovery, delete or cleanup work,
   broad file edits, or agent-heavy work
3. use scratch/worktrees only as secondaries
4. if a scratch/worktree produces valuable local-only artifacts, snapshot or
   migrate them back to the canonical repo quickly
5. leave Codex's local home/config on C drive unless there is a separate,
   explicit configuration migration task

### Optional promoted mainlines

If you want focused working directories outside the monorepo, promote them under:

- `D:\Users\rickylu\dev\financial-services-docs`
- `D:\Users\rickylu\dev\financial-services-stock`
- `D:\Users\rickylu\dev\financial-services-obsidian`

Use:

```powershell
.\scripts\promote-mainlines.ps1
.\scripts\promote-mainlines.ps1 -Execute
```

These are safe lifted copies for focused workstreams. They do not replace the
canonical repo unless you intentionally adopt them as separate projects.

### Best practical WSL model

1. keep the canonical repo under Linux home, for example `/home/<you>/dev/...`
2. use Windows tools only when necessary
3. avoid keeping the primary repo in Windows temp/scratch paths
4. still snapshot important local-only artifacts back to a Windows-accessible
   backup root if they matter operationally

## Minimal Habits That Prevent Repeat Loss

1. Before any file-mutating or risky tool session, run:

```powershell
.\scripts\repo-snapshot.ps1 -BackupRoot "D:\Users\rickylu\repo-safety-backups\financial-services-plugins" -MirrorLatest -IncludeGit
```

2. Before executing a delete, cleanup, move, rename, rollback, or bulk write,
   run the dry-run or preview mode first and review the candidate list.

3. Do not edit or prune the backup root during normal task work.

4. Before adopting a new workspace path, run:

```powershell
.\scripts\check-workspace-safety.ps1
```

5. If the repo is in scratch, migrate it as soon as the current task stabilizes.

6. Treat `.tmp/` as recoverable state until proven disposable.

7. Do not assume agent scratch space is a safe long-term home, even if it feels
   convenient.
