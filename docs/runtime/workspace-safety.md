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

### 2. Create a snapshot outside the workspace

```powershell
.\scripts\repo-snapshot.ps1
```

Defaults:

- creates a timestamped snapshot outside the repo under the user profile
- writes a manifest file
- does not include `.git` unless explicitly requested

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

### 3. Prepare a stable canonical workspace

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
2. take snapshots before risky recovery or agent-heavy work
3. use scratch/worktrees only as secondaries
4. if a scratch/worktree produces valuable local-only artifacts, snapshot or
   migrate them back to the canonical repo quickly

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

1. Before a risky tool session, run:

```powershell
.\scripts\repo-snapshot.ps1 -MirrorLatest
```

2. Before adopting a new workspace path, run:

```powershell
.\scripts\check-workspace-safety.ps1
```

3. If the repo is in scratch, migrate it as soon as the current task stabilizes.

4. Treat `.tmp/` as recoverable state until proven disposable.

5. Do not assume agent scratch space is a safe long-term home, even if it feels
   convenient.
