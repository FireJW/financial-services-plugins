# Obsidian KB Local

## Operating Contract

- 这个目录是 Codex 到 Obsidian CLI 的控制面。
- 默认目标 Vault 是 `D:\OneDrive - zn\文档\Obsidian Vault`。
- 默认机器写入边界是 `08-AI知识库`。
- 不要直接修改 `00-07` 目录，除非用户明确要求。
- 优先运行封装脚本，而不是临时手写原始 CLI 命令。

## Preferred Commands

- `cmd /c npm run doctor`
- `cmd /c npm run bootstrap-vault`
- `cmd /c npm run write-smoke`
- `cmd /c npm run obsidian -- <command>`

## Write Rules

- 新建或覆盖 note 时，优先用 Obsidian CLI。
- 必要时允许用文件系统创建目录，但文件内容写入优先通过 CLI 完成。
- 所有测试默认不触碰真实 Vault，除非用户明确要求跑真实写入 smoke。

