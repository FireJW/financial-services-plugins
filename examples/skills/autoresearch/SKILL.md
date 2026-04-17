---
name: autoresearch
description: |
  Wrapper skill for karpathy/autoresearch. Use when you want Codex to operate
  inside the local autoresearch research project, following the upstream
  program.md workflow and respecting its GPU and environment constraints.
---

# autoresearch

This local skill wraps the upstream `karpathy/autoresearch` project.

## What This Is

`autoresearch` is not a standard Codex skill repository. It is a Python/GPU
research project that includes:

- `program.md`: upstream agent instructions
- `prepare.py`: data preparation
- `train.py`: training loop to iterate on
- `pyproject.toml` and `uv.lock`: dependency management

When using this skill:

1. Read `README.md`.
2. Read `program.md`.
3. Check whether the machine has the required runtime before attempting any run.

## Constraints

- Prefer `uv` for environment and execution.
- Assume NVIDIA GPU is required unless the local project has been adapted.
- On this Windows machine, be careful about caches landing on `C:` by default.
- Do not start expensive downloads or training runs unless the user asked for it.

## Typical Commands

- `uv sync`
- `uv run prepare.py`
- `uv run train.py`

## Local Notes

- If the local checkout is on `D:\Users\rickylu\.codex\skills\autoresearch`,
  keep project files there.
- If a junction exists at `C:\Users\rickylu\.codex\skills\autoresearch`, use it
  as the Codex-visible entrypoint.
