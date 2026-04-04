import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { generateFrontmatter } from "../src/frontmatter.mjs";
import {
  collectRollbackCandidates,
  executeRollback,
  isProtectedRollbackPath,
  writeRollbackLog
} from "../src/rollback.mjs";

describe("rollback helpers", () => {
  it("recognizes protected paths", () => {
    assert.equal(isProtectedRollbackPath("08-ai-kb/10-raw/README.md"), true);
    assert.equal(isProtectedRollbackPath("08-ai-kb/20-wiki/sources/Example.md"), false);
  });

  it("collects only codex-managed notes and deletes them safely", () => {
    const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-rollback-test-"));

    try {
      const config = createRollbackFixture(tempRoot);
      const candidates = collectRollbackCandidates(config, {
        topic: "LLM Knowledge Bases"
      });

      assert.equal(candidates.length, 1);
      assert.match(candidates[0].relativePath, /Generated-Note\.md$/);

      const logFile = writeRollbackLog(config.projectRoot, {
        topic: "LLM Knowledge Bases",
        candidates,
        timestamp: "2026-04-04T12:00:00Z"
      });
      assert.ok(fs.existsSync(logFile));

      const deleted = executeRollback(config, candidates);
      assert.equal(deleted, 1);
      assert.equal(fs.existsSync(candidates[0].fullPath), false);
      assert.equal(
        fs.existsSync(
          path.join(config.vaultPath, config.machineRoot, "10-raw", "manual", "Human-Note.md")
        ),
        true
      );
    } finally {
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  });
});

function createRollbackFixture(tempRoot) {
  const vaultPath = path.join(tempRoot, "vault");
  const machineRoot = "08-ai-kb";
  const projectRoot = tempRoot;

  const generatedPath = path.join(
    vaultPath,
    machineRoot,
    "20-wiki",
    "sources",
    "Generated-Note.md"
  );
  const humanPath = path.join(
    vaultPath,
    machineRoot,
    "10-raw",
    "manual",
    "Human-Note.md"
  );
  const readmePath = path.join(vaultPath, machineRoot, "20-wiki", "README.md");

  fs.mkdirSync(path.dirname(generatedPath), { recursive: true });
  fs.mkdirSync(path.dirname(humanPath), { recursive: true });

  fs.writeFileSync(
    generatedPath,
    `${generateFrontmatter("wiki", {
      wiki_kind: "source",
      topic: "LLM Knowledge Bases",
      compiled_from: ["08-ai-kb/10-raw/web/example.md"],
      compiled_at: "2026-04-04T10:00:00+08:00",
      kb_date: "2026-04-04",
      review_state: "draft",
      kb_source_count: 1,
      dedup_key: "llm knowledge bases::source::https://example.com"
    })}

# Generated Note

Machine-generated content.
`,
    "utf8"
  );

  fs.writeFileSync(
    humanPath,
    `${generateFrontmatter("raw", {
      source_type: "manual",
      topic: "LLM Knowledge Bases",
      source_url: "",
      captured_at: "2026-04-04T09:00:00+08:00",
      kb_date: "2026-04-04",
      status: "queued"
    })}

# Human Note

Human-managed content.
`,
    "utf8"
  );

  fs.writeFileSync(readmePath, "# README\n", "utf8");

  return {
    vaultPath,
    vaultName: "Test Vault",
    machineRoot,
    projectRoot,
    obsidian: {
      cliCandidates: [],
      exeCandidates: []
    }
  };
}
