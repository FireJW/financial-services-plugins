import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { parseFrontmatter, validateRawFrontmatter } from "../src/frontmatter.mjs";
import {
  createDefaultXAuthorEntry,
  extractXHandleFromUrl,
  inspectXSourceUrl,
  upsertXAuthorEntry
} from "../src/x-source-registry.mjs";
import {
  buildPromotedXRawNote,
  importXIndexPosts,
  selectXPostsForPromotion
} from "../src/x-index-import.mjs";

test("x source registry normalizes handles and allowlist inspection", () => {
  assert.equal(extractXHandleFromUrl("https://x.com/Ariston_Macro/status/2041091494116003853"), "Ariston_Macro");
  assert.equal(extractXHandleFromUrl("https://twitter.com/karpathy/status/123"), "karpathy");
  assert.equal(extractXHandleFromUrl("https://example.com/not-x"), "");

  const registry = {
    authors: [createDefaultXAuthorEntry({ handle: "z_handle", addedAt: "2026-04-06T00:00:00+08:00" })]
  };
  const next = upsertXAuthorEntry(
    registry,
    createDefaultXAuthorEntry({ handle: "@AlphaDesk/", addedAt: "2026-04-06T00:00:00+08:00" })
  );
  assert.deepEqual(next.authors.map((entry) => entry.handle), ["AlphaDesk", "z_handle"]);

  assert.equal(inspectXSourceUrl("https://x.com/AlphaDesk/status/1", next).isAllowlisted, true);
  assert.equal(inspectXSourceUrl("https://x.com/NewMacroDesk/status/2", next).shouldPromptToWhitelist, true);
});

test("x index import selects and writes promoted raw notes", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-x-index-focused-"));
  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      machineRoot: "08-ai-kb",
      obsidian: { cliCandidates: [], exeCandidates: [] }
    };
    const registry = {
      default_policy: {
        promoted_bucket: "08-ai-kb/10-raw/web/x-promoted"
      },
      authors: [createDefaultXAuthorEntry({ handle: "LinQingV" })]
    };
    const result = {
      request: {
        topic: "LinQingV auto analysis",
        analysis_time: "2026-04-06T13:40:00+00:00",
        keywords: ["BYD", "SAIC"]
      },
      x_posts: [
        {
          post_url: "https://x.com/LinQingV/status/2041135310852235487",
          author_handle: "LinQingV",
          author_display_name: "LinQingV",
          posted_at: "2026-04-06T12:45:55+00:00",
          post_text_raw: "BYD SAIC analysis",
          post_summary: "auto analysis summary",
          artifact_manifest: [{ role: "root_post_screenshot", path: "C:/tmp/root.png" }]
        },
        {
          post_url: "https://x.com/LinQingV/status/2041015554740543812",
          author_handle: "LinQingV",
          post_text_raw: "shipping note"
        }
      ]
    };

    assert.equal(selectXPostsForPromotion(result, { postIds: ["2041135310852235487"] }).length, 1);
    const note = buildPromotedXRawNote(config, result, result.x_posts[0], { registry });
    assert.equal(note.path, "08-ai-kb/10-raw/web/x-promoted/LinQingV-2041135310852235487.md");
    assert.match(note.content, /Allowlist status: allowlisted/);

    const writes = importXIndexPosts(config, result, {
      registry,
      postIds: ["2041135310852235487"],
      preferCli: false,
      allowFilesystemFallback: true
    });
    assert.equal(writes.length, 1);
    const frontmatter = parseFrontmatter(fs.readFileSync(path.join(config.vaultPath, writes[0].path), "utf8"));
    assert.doesNotThrow(() => validateRawFrontmatter(frontmatter));
    assert.equal(frontmatter.topic, "LinQingV auto analysis");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});
