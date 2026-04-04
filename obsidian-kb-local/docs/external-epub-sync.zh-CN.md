# 外部 EPUB 资料接入 Obsidian Raw 层

这套接入是“外部路径索引”模式，不复制 `.epub` 本体进 Vault。

## 目标

- 扫描本地 EPUB 目录
- 在 `08-AI知识库/10-raw/books/` 下创建对应的 raw note
- raw note 只保存绝对路径、文件 URI、文件大小、修改时间和检索说明
- 原始 `.epub` 继续留在原目录，不搬进 Obsidian，也不塞进仓库
- 这些 note 仍可参与自动双链和后续主题检索

## 默认扫描路径

- `D:\下载`
- `D:\桌面书单`

也可以手动传入别的根目录。

## 推荐命令

先做 dry-run 看看会索引多少本：

```powershell
cmd /c "cd obsidian-kb-local && npm run import-epub-library -- --dry-run"
```

正式导入默认路径下的 EPUB：

```powershell
cmd /c "cd obsidian-kb-local && npm run import-epub-library"
```

只导入某几个目录，并限制数量：

```powershell
cmd /c "cd obsidian-kb-local && npm run import-epub-library -- --root \"D:\下载\" --root \"D:\桌面书单\" --limit 100"
```

如果你希望它们进入后续编译队列，而不是只做索引：

```powershell
cmd /c "cd obsidian-kb-local && npm run import-epub-library -- --status queued"
```

## 默认状态为什么是 archived

EPUB 这次采用的是轻量索引，不是全文复制。

所以默认写成 `status: archived`，含义是：

- 已经纳入 raw 资料层
- 可以被搜索、引用、双链关联
- 但不会一下子冲进当前的 `queued` 编译队列

这样更适合大量书籍的本地资料库。

## note 里会写什么

每本书的 raw note 会包含：

- 本地绝对路径
- `file:///` URI
- 所属根目录
- 相对路径
- 文件大小
- 最后修改时间
- 这是“外部路径引用，不复制本体”的说明

## 不会发生什么

- 不会把 `.epub` 复制进 Vault
- 不会把 `.epub` 放进仓库
- 不会让 Obsidian Vault 因为二进制书库而爆炸式变大

## 与双链的关系

现在 `rebuild-links` 会把 `10-raw/books/` 也纳入扫描。

这意味着：

- 书目 note 可以和已有 article/wiki note 建立 `## Related`
- 如果书名、topic、标题词和现有概念 note 重合，就能逐步形成图谱

## 之后可以继续增强的方向

如果你后面觉得“只有路径索引还不够”，下一步最自然的是做按需提取，而不是全量复制：

1. 只提取封面、目录、元数据
2. 只提取前几章或指定章节
3. 只为某本高价值书生成摘要 note

这样依旧能保持 Vault 轻量。 
