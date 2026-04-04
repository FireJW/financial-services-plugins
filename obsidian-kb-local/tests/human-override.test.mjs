import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  extractHumanOverrides,
  hasHumanOverrides,
  mergeWithOverrides
} from "../src/human-override.mjs";

describe("extractHumanOverrides", () => {
  it("extracts a single override block", () => {
    const content = `# Title

Body

<!-- human-override -->
My custom note
<!-- /human-override -->
`;

    const overrides = extractHumanOverrides(content);
    assert.equal(overrides.length, 1);
    assert.match(overrides[0].innerContent, /My custom note/);
  });

  it("extracts multiple override blocks", () => {
    const content = `<!-- human-override -->
Block 1
<!-- /human-override -->

Middle

<!-- human-override -->
Block 2
<!-- /human-override -->`;

    const overrides = extractHumanOverrides(content);
    assert.equal(overrides.length, 2);
    assert.match(overrides[0].innerContent, /Block 1/);
    assert.match(overrides[1].innerContent, /Block 2/);
  });

  it("returns an empty array when no override exists", () => {
    assert.deepEqual(extractHumanOverrides("# Just content"), []);
  });
});

describe("mergeWithOverrides", () => {
  it("appends old overrides when new content has none", () => {
    const merged = mergeWithOverrides("# Updated\n\nNew body.", [
      {
        fullMatch: "<!-- human-override -->\nMy custom note\n<!-- /human-override -->",
        innerContent: "\nMy custom note\n",
        index: 0
      }
    ]);

    assert.match(merged, /New body\./);
    assert.match(merged, /My custom note/);
    assert.match(merged, /<!-- human-override -->/);
  });

  it("returns new content unchanged when there are no existing overrides", () => {
    const content = "# Title\n\nContent.";
    assert.equal(mergeWithOverrides(content, []), content);
  });

  it("preserves override blocks already present in new content", () => {
    const newContent = `# Title

<!-- human-override -->
Already present
<!-- /human-override -->`;

    const merged = mergeWithOverrides(newContent, [
      {
        fullMatch: "<!-- human-override -->\nOld override\n<!-- /human-override -->",
        innerContent: "\nOld override\n",
        index: 0
      }
    ]);

    assert.match(merged, /Already present/);
    assert.doesNotMatch(merged, /Old override/);
  });
});

describe("hasHumanOverrides", () => {
  it("returns true when content has overrides", () => {
    assert.equal(
      hasHumanOverrides("a <!-- human-override -->x<!-- /human-override --> b"),
      true
    );
  });

  it("returns false when content has no overrides", () => {
    assert.equal(hasHumanOverrides("# Normal"), false);
  });

  it("returns false for null", () => {
    assert.equal(hasHumanOverrides(null), false);
  });
});
