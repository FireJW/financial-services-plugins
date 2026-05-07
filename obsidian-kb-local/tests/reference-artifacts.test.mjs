import assert from "node:assert/strict";
import test from "node:test";
import {
  buildReferenceHubCompiledFrom,
  extractLinkedWikiPathsFromSection
} from "../src/reference-artifacts.mjs";

test("reference hub uses deduped wiki note paths and extracts links from a section", () => {
  assert.deepEqual(
    buildReferenceHubCompiledFrom([
      { path: "08-ai-kb/20-wiki/sources/A-reference-map.md" },
      { path: "08-ai-kb/20-wiki/sources/B-reference-map.md" },
      { path: "08-ai-kb/20-wiki/sources/A-reference-map.md" },
      { path: "08-ai-kb/10-raw/books/ignored.md" }
    ]),
    [
      "08-ai-kb/20-wiki/sources/A-reference-map.md",
      "08-ai-kb/20-wiki/sources/B-reference-map.md"
    ]
  );

  const body = `# Finance Book Reference Hub

## Book Maps

- [[08-ai-kb/20-wiki/sources/A-reference-map|A]]
- [[08-ai-kb/20-wiki/sources/B-reference-map.md|B]]

## Search Seeds

- ignored
`;

  assert.deepEqual(extractLinkedWikiPathsFromSection(body, "Book Maps"), [
    "08-ai-kb/20-wiki/sources/A-reference-map.md",
    "08-ai-kb/20-wiki/sources/B-reference-map.md"
  ]);
});
