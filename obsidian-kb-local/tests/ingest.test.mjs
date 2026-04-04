import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { ingestRawNote, sanitizeFilename } from "../src/ingest.mjs";
import { parseFrontmatter, validateRawFrontmatter } from "../src/frontmatter.mjs";

describe("sanitizeFilename", () => {
  it("removes filesystem-invalid characters and normalizes spaces", () => {
    assert.equal(
      sanitizeFilename('  Article: "CLI/Obsidian" <Draft>?  '),
      "Article-CLIObsidian-Draft"
    );
  });

  it("falls back when the title becomes empty", () => {
    assert.equal(sanitizeFilename('<<>>:"/\\\\|?*'), "untitled-note");
  });
});

describe("ingestRawNote", () => {
  it("writes a v2 raw note into the web lane with filesystem fallback", () => {
    const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-ingest-test-"));

    try {
      const config = {
        vaultPath: tempRoot,
        vaultName: "Test Vault",
        machineRoot: "08-ai-kb",
        obsidian: {
          cliCandidates: [],
          exeCandidates: []
        }
      };

      const result = ingestRawNote(
        config,
        {
          sourceType: "web_article",
          topic: "LLM Knowledge Bases",
          sourceUrl: "https://example.com/article",
          title: 'Karpathy: "LLM/Knowledge Bases"?',
          body: "Captured from a test harness."
        },
        {
          preferCli: false,
          allowFilesystemFallback: true
        }
      );

      assert.equal(result.mode, "filesystem-fallback");
      assert.equal(
        result.path,
        "08-ai-kb/10-raw/web/Karpathy-LLMKnowledge-Bases.md"
      );

      const writtenContent = fs.readFileSync(path.join(tempRoot, result.path), "utf8");
      const frontmatter = parseFrontmatter(writtenContent);

      assert.ok(frontmatter);
      assert.doesNotThrow(() => validateRawFrontmatter(frontmatter));
      assert.match(writtenContent, /^# Karpathy: "LLM\/Knowledge Bases"\?/m);
      assert.match(writtenContent, /Captured from a test harness\./);
    } finally {
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  });

  it("rejects unknown source types before writing", () => {
    assert.throws(
      () =>
        ingestRawNote(
          {
            vaultPath: "C:/vault",
            vaultName: "Test Vault",
            machineRoot: "08-ai-kb",
            obsidian: {
              cliCandidates: [],
              exeCandidates: []
            }
          },
          {
            sourceType: "podcast",
            topic: "LLM Knowledge Bases",
            title: "Episode 1",
            body: "test"
          },
          {
            preferCli: false,
            allowFilesystemFallback: true
          }
        ),
      /Unknown sourceType/
    );
  });
});
