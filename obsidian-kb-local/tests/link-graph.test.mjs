import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import test from "node:test";
import {
  applyRelatedSection,
  buildRelatedGraph,
  collectLinkableNotes,
  rebuildAutomaticLinks
} from "../src/link-graph.mjs";
import { generateFrontmatter } from "../src/frontmatter.mjs";

test("buildRelatedGraph links notes that mention each other or share topic", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Claude-Code.md",
      title: "Claude Code",
      topic: "claude code",
      cleanBody: "Claude Code can drive Chrome.",
      tokens: new Set(["claude", "code"])
    },
    {
      relativePath: "08-ai-kb/10-raw/articles/Claude-Code-Hidden-Features.md",
      title: "Claude Code Hidden Features",
      topic: "claude code",
      cleanBody: "This article covers Claude Code and Chrome automation.",
      tokens: new Set(["claude", "code", "chrome"])
    }
  ];

  const graph = buildRelatedGraph(notes, {
    maxLinks: 8,
    minScore: 4
  });

  assert.equal(graph.get(notes[0].relativePath).length, 1);
  assert.equal(graph.get(notes[1].relativePath).length, 1);
});

test("buildRelatedGraph ignores shared template headings across unrelated raw notes", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/10-raw/books/Deep-Work.md",
      title: "Deep Work",
      topic: "Deep Work",
      cleanBody: "## External File\n## Book Metadata\n## Retrieval Notes",
      content: "# Deep Work\n\n## External File\n\n## Book Metadata\n\n## Retrieval Notes",
      frontmatter: {
        kb_type: "raw",
        source_type: "epub",
        topic: "Deep Work"
      },
      tokens: new Set(["deep", "work"])
    },
    {
      relativePath: "08-ai-kb/10-raw/books/Monetary-History.md",
      title: "Monetary History",
      topic: "Monetary History",
      cleanBody: "## External File\n## Book Metadata\n## Retrieval Notes",
      content: "# Monetary History\n\n## External File\n\n## Book Metadata\n\n## Retrieval Notes",
      frontmatter: {
        kb_type: "raw",
        source_type: "epub",
        topic: "Monetary History"
      },
      tokens: new Set(["monetary", "history"])
    }
  ];

  const graph = buildRelatedGraph(notes, {
    maxLinks: 8,
    minScore: 4
  });

  assert.equal(graph.get(notes[0].relativePath).length, 0);
  assert.equal(graph.get(notes[1].relativePath).length, 0);
});

test("applyRelatedSection replaces the managed link block idempotently", () => {
  const original = "# Test\n\nBody.\n";
  const updated = applyRelatedSection(original, [
    {
      note: {
        relativePath: "08-ai-kb/20-wiki/concepts/Claude-Code.md",
        title: "Claude Code"
      },
      score: 10
    }
  ]);
  const rerun = applyRelatedSection(updated, [
    {
      note: {
        relativePath: "08-ai-kb/20-wiki/concepts/Claude-Code.md",
        title: "Claude Code"
      },
      score: 10
    }
  ]);

  assert.match(updated, /\[\[08-ai-kb\/20-wiki\/concepts\/Claude-Code\|Claude Code\]\]/);
  assert.equal(updated, rerun);
});

test("rebuildAutomaticLinks updates wiki and article notes inside the vault", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-link-graph-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };

    const articlePath = path.join(
      config.vaultPath,
      config.machineRoot,
      "10-raw",
      "articles",
      "Claude-Code-Hidden-Features.md"
    );
    const conceptPath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "concepts",
      "Claude-Code.md"
    );

    fs.mkdirSync(path.dirname(articlePath), { recursive: true });
    fs.mkdirSync(path.dirname(conceptPath), { recursive: true });

    fs.writeFileSync(
      articlePath,
      `${generateFrontmatter("raw", {
        source_type: "article",
        topic: "Claude Code",
        source_url: "workflow://article-corpus/claude-code-hidden-features",
        captured_at: "2026-04-04T10:00:00+08:00",
        kb_date: "2026-04-04",
        status: "queued"
      })}

# Claude Code Hidden Features

Claude Code can drive Chrome and other tools.
`,
      "utf8"
    );

    fs.writeFileSync(
      conceptPath,
      `${generateFrontmatter("wiki", {
        wiki_kind: "concept",
        topic: "Claude Code",
        compiled_from: ["08-ai-kb/10-raw/articles/Claude-Code-Hidden-Features.md"],
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04",
        review_state: "draft",
        kb_source_count: 1,
        dedup_key: "claude code::concept::title:claude-code"
      })}

# Claude Code

Chrome automation is one visible surface.
`,
      "utf8"
    );

    const collected = collectLinkableNotes(config.vaultPath, config.machineRoot);
    assert.equal(collected.length, 2);

    const result = rebuildAutomaticLinks(config, {
      preferCli: false,
      allowFilesystemFallback: true
    });

    assert.equal(result.updated, 2);
    const articleContent = fs.readFileSync(articlePath, "utf8");
    const conceptContent = fs.readFileSync(conceptPath, "utf8");
    assert.match(articleContent, /\[\[08-ai-kb\/20-wiki\/concepts\/Claude-Code\|Claude Code\]\]/);
    assert.match(
      conceptContent,
      /\[\[08-ai-kb\/10-raw\/articles\/Claude-Code-Hidden-Features\|Claude Code Hidden Features\]\]/
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("collectLinkableNotes includes epub raw notes from the books lane", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-link-graph-epub-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };

    const bookPath = path.join(
      config.vaultPath,
      config.machineRoot,
      "10-raw",
      "books",
      "Deep-Work--abc12345.md"
    );
    fs.mkdirSync(path.dirname(bookPath), { recursive: true });
    fs.writeFileSync(
      bookPath,
      `${generateFrontmatter("raw", {
        source_type: "epub",
        topic: "Deep Work",
        source_url: "file:///D:/books/deep-work.epub",
        captured_at: "2026-04-04T10:00:00+08:00",
        kb_date: "2026-04-04",
        status: "archived"
      })}

# Deep Work

Deep Work discusses focused attention and distraction control.
`,
      "utf8"
    );

    const collected = collectLinkableNotes(config.vaultPath, config.machineRoot);
    assert.equal(collected.length, 1);
    assert.equal(collected[0].frontmatter.source_type, "epub");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});
