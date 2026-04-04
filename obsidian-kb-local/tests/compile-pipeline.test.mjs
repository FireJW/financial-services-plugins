import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  applyCompileOutput,
  buildCompilePrompt,
  buildHealthCheckReport
} from "../src/compile-pipeline.mjs";
import {
  generateFrontmatter,
  parseFrontmatter,
  validateRawFrontmatter,
  validateWikiFrontmatter
} from "../src/frontmatter.mjs";

describe("compile pipeline", () => {
  it("builds prompt text with raw content and existing wiki context", () => {
    const template = "RAW={{RAW_CONTENT}}\nTOPIC={{TOPIC}}\nNOTES={{EXISTING_NOTES}}";
    const rawNote = {
      content: "---\nkb_type: raw\n---\n\n# Raw",
      frontmatter: {
        topic: "LLM Knowledge Bases"
      }
    };
    const existingWikiNotes = [
      {
        title: "Source Overview",
        relativePath: "08-ai-kb/20-wiki/sources/Source-Overview.md",
        frontmatter: {
          wiki_kind: "source",
          compiled_from: ["08-ai-kb/10-raw/web/one.md"]
        }
      }
    ];

    const prompt = buildCompilePrompt(template, rawNote, existingWikiNotes);
    assert.match(prompt, /RAW=---/);
    assert.match(prompt, /TOPIC=LLM Knowledge Bases/);
    assert.match(prompt, /Source Overview \(source\)/);
  });

  it("applies compiled notes, updates raw status, and writes logs", () => {
    const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-compile-pipeline-"));

    try {
      const { config, rawPath } = createFixtureVault(tempRoot);
      const timestamp = "2026-04-04T12:00:00+08:00";

      const result = applyCompileOutput(
        config,
        {
          rawPath,
          notes: [
            {
              wiki_kind: "source",
              title: "Karpathy Source",
              topic: "LLM Knowledge Bases",
              body: "## Summary\n\nA source summary.",
              source_url: "https://example.com/article"
            },
            {
              wiki_kind: "concept",
              title: "LLM Knowledge Bases",
              topic: "LLM Knowledge Bases",
              body: "## Key points\n\nA reusable concept."
            }
          ]
        },
        {
          timestamp,
          preferCli: false,
          allowFilesystemFallback: true
        }
      );

      assert.equal(result.rawStatus, "compiled");
      assert.equal(result.results.length, 2);

      const rawContent = fs.readFileSync(path.join(config.vaultPath, rawPath), "utf8");
      const rawFrontmatter = parseFrontmatter(rawContent);
      assert.doesNotThrow(() => validateRawFrontmatter(rawFrontmatter));
      assert.equal(rawFrontmatter.status, "compiled");

      const sourcePath = path.join(
        config.vaultPath,
        config.machineRoot,
        "20-wiki",
        "sources",
        "Karpathy-Source.md"
      );
      const sourceContent = fs.readFileSync(sourcePath, "utf8");
      const sourceFrontmatter = parseFrontmatter(sourceContent);
      assert.doesNotThrow(() => validateWikiFrontmatter(sourceFrontmatter));
      assert.deepEqual(sourceFrontmatter.compiled_from, [rawPath]);
      assert.equal(sourceFrontmatter.kb_source_count, 1);

      const logFile = path.join(tempRoot, "logs", "compile-2026-04-04.jsonl");
      assert.equal(result.logFile, logFile);
      assert.ok(fs.existsSync(logFile));
      assert.match(fs.readFileSync(logFile, "utf8"), /Karpathy-Source\.md/);
    } finally {
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  });

  it("updates existing wiki notes in place and preserves human overrides", () => {
    const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-compile-override-"));

    try {
      const { config, rawPath } = createFixtureVault(tempRoot);
      const existingWikiPath = path.join(
        config.vaultPath,
        config.machineRoot,
        "20-wiki",
        "sources",
        "Karpathy-Source.md"
      );
      fs.mkdirSync(path.dirname(existingWikiPath), { recursive: true });

      const existingFrontmatter = generateFrontmatter("wiki", {
        wiki_kind: "source",
        topic: "LLM Knowledge Bases",
        compiled_from: [rawPath],
        compiled_at: "2026-04-03T12:00:00+08:00",
        kb_date: "2026-04-03",
        review_state: "draft",
        kb_source_count: 1,
        dedup_key: "llm knowledge bases::source::https://example.com/article"
      });
      fs.writeFileSync(
        existingWikiPath,
        `${existingFrontmatter}

# Karpathy Source

## Summary

Old content.

<!-- human-override -->
Keep this manual annotation.
<!-- /human-override -->
`,
        "utf8"
      );

      applyCompileOutput(
        config,
        {
          rawPath,
          notes: [
            {
              wiki_kind: "source",
              title: "Karpathy Source",
              topic: "LLM Knowledge Bases",
              body: "## Summary\n\nNew compiled content.",
              source_url: "https://example.com/article"
            }
          ]
        },
        {
          timestamp: "2026-04-04T12:30:00+08:00",
          preferCli: false,
          allowFilesystemFallback: true
        }
      );

      const updatedContent = fs.readFileSync(existingWikiPath, "utf8");
      assert.match(updatedContent, /New compiled content\./);
      assert.match(updatedContent, /Keep this manual annotation\./);
    } finally {
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  });

  it("reports stale notes, missing sources, orphans, and dedup conflicts", () => {
    const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-health-check-"));

    try {
      const { config, rawPath } = createFixtureVault(tempRoot);
      const wikiRoot = path.join(config.vaultPath, config.machineRoot, "20-wiki");
      fs.mkdirSync(path.join(wikiRoot, "sources"), { recursive: true });
      fs.mkdirSync(path.join(wikiRoot, "concepts"), { recursive: true });

      fs.writeFileSync(
        path.join(wikiRoot, "sources", "Stale-Source.md"),
        buildWikiFixture({
          wiki_kind: "source",
          topic: "LLM Knowledge Bases",
          compiled_from: [rawPath],
          compiled_at: "2026-04-03T12:00:00+08:00",
          kb_date: "2026-04-03",
          kb_source_count: 1,
          dedup_key: "llm knowledge bases::source::https://example.com/article",
          title: "Stale Source",
          body: "## Summary\n\nStale content."
        }),
        "utf8"
      );

      fs.writeFileSync(
        path.join(wikiRoot, "sources", "Missing-Source.md"),
        buildWikiFixture({
          wiki_kind: "source",
          topic: "LLM Knowledge Bases",
          compiled_from: ["08-ai-kb/10-raw/web/missing.md"],
          compiled_at: "2026-04-04T11:00:00+08:00",
          kb_date: "2026-04-04",
          kb_source_count: 1,
          dedup_key: "llm knowledge bases::source::https://example.com/article",
          title: "Missing Source",
          body: "## Summary\n\nMissing source."
        }),
        "utf8"
      );

      fs.writeFileSync(
        path.join(wikiRoot, "concepts", "Orphan-Concept.md"),
        buildWikiFixture({
          wiki_kind: "concept",
          topic: "LLM Knowledge Bases",
          compiled_from: [],
          compiled_at: "2026-04-04T11:00:00+08:00",
          kb_date: "2026-04-04",
          kb_source_count: 0,
          dedup_key: "llm knowledge bases::concept::title:orphan-concept",
          title: "Orphan Concept",
          body: "## Key points\n\nOrphan."
        }),
        "utf8"
      );

      const { report } = buildHealthCheckReport(config);
      assert.equal(report.missing_source.length, 1);
      assert.equal(report.orphan_wiki.length, 1);
      assert.ok(report.stale_wiki.length >= 1);
      assert.equal(report.dedup_conflicts.length, 1);
      assert.match(report.summary, /Health check found/);
    } finally {
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  });
});

function createFixtureVault(tempRoot) {
  const vaultPath = path.join(tempRoot, "vault");
  const machineRoot = "08-ai-kb";
  const rawPath = `${machineRoot}/10-raw/web/karpathy-article.md`;
  const fullRawPath = path.join(vaultPath, rawPath);
  fs.mkdirSync(path.dirname(fullRawPath), { recursive: true });

  const rawFrontmatter = generateFrontmatter("raw", {
    source_type: "web_article",
    topic: "LLM Knowledge Bases",
    source_url: "https://example.com/article",
    captured_at: "2026-04-04T10:00:00+08:00",
    kb_date: "2026-04-04",
    status: "queued"
  });
  fs.writeFileSync(
    fullRawPath,
    `${rawFrontmatter}

# Raw article

Body of the source note.
`,
    "utf8"
  );

  return {
    config: {
      vaultPath,
      vaultName: "Test Vault",
      machineRoot,
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    },
    rawPath
  };
}

function buildWikiFixture(fields) {
  const frontmatter = generateFrontmatter("wiki", {
    wiki_kind: fields.wiki_kind,
    topic: fields.topic,
    compiled_from: fields.compiled_from,
    compiled_at: fields.compiled_at,
    kb_date: fields.kb_date,
    review_state: "draft",
    kb_source_count: fields.kb_source_count,
    dedup_key: fields.dedup_key
  });

  return `${frontmatter}

# ${fields.title}

${fields.body}
`;
}
