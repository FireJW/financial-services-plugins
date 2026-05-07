import assert from "node:assert/strict";
import test from "node:test";
import {
  buildEpubCompileDigest,
  buildEpubCompilePromptVariants,
  convertXhtmlToMarkdown,
  isFinanceRelatedBookCandidate,
  parseContainerRootfile,
  parseOpfPackage,
  selectFinanceRelatedBookNotes
} from "../src/epub-markdown.mjs";

test("epub markdown helpers parse container, opf, and chapter xhtml", () => {
  assert.equal(
    parseContainerRootfile(`<container><rootfiles><rootfile full-path="OEBPS/content.opf" /></rootfiles></container>`),
    "OEBPS/content.opf"
  );

  const packageDoc = parseOpfPackage(`<package>
    <metadata>
      <dc:title>Money &amp; Banking</dc:title>
      <dc:creator>Jane Doe</dc:creator>
      <dc:description>Central bank basics</dc:description>
    </metadata>
    <manifest>
      <item id="nav" href="nav.xhtml" />
      <item id="ch1" href="text/ch1.xhtml" media-type="application/xhtml+xml" />
    </manifest>
    <spine>
      <itemref idref="nav" linear="no" />
      <itemref idref="ch1" />
    </spine>
  </package>`);

  assert.equal(packageDoc.metadata.title, "Money & Banking");
  assert.equal(packageDoc.metadata.creator, "Jane Doe");
  assert.equal(packageDoc.metadata.description, "Central bank basics");
  assert.equal(packageDoc.manifest.get("ch1").href, "text/ch1.xhtml");
  assert.deepEqual(packageDoc.spine, ["ch1"]);

  const markdown = convertXhtmlToMarkdown(`<html><body>
    <p class="cn">1</p>
    <p class="ct">THE GREAT INFLATION</p>
    <p>First paragraph.</p>
    <blockquote>Quoted line.</blockquote>
    <li>Bullet item</li>
    <p class="h1">Second Chapter</p>
  </body></html>`);

  assert.match(markdown, /^## 1 THE GREAT INFLATION/m);
  assert.match(markdown, /First paragraph\./);
  assert.match(markdown, /^> Quoted line\./m);
  assert.match(markdown, /^- Bullet item/m);
  assert.equal(markdown.includes("Bullet item\n\n## Second Chapter"), true);
});

test("finance selector ignores related-link pollution and prefers extracted notes", () => {
  assert.equal(
    isFinanceRelatedBookCandidate({
      title: "The Book of Elon",
      frontmatter: { topic: "The Book of Elon" },
      sourcePath: "D:/books/The Book of Elon.epub",
      body: "## Related\n\n- [[How to Make Money in Stocks|How to Make Money in Stocks]]",
      hasExtractedMarkdown: false
    }),
    false
  );

  const selected = selectFinanceRelatedBookNotes([
    {
      title: "Money Origins",
      frontmatter: { topic: "Money Origins" },
      sourcePath: "D:/books/Money-Origins.epub",
      body: "# Money Origins",
      hasExtractedMarkdown: false
    },
    {
      title: "Money Origins",
      frontmatter: { topic: "Money Origins" },
      sourcePath: "D:/desktop-books/Money-Origins.epub",
      body: "# Money Origins",
      hasExtractedMarkdown: true
    }
  ]);

  assert.equal(selected.length, 1);
  assert.equal(selected[0].sourcePath, "D:/desktop-books/Money-Origins.epub");
});

test("epub compile digest keeps section coverage within configured size", () => {
  const rawNote = {
    title: "Long Book",
    frontmatter: {
      topic: "Long Book",
      source_url: "file:///D:/books/long-book.epub"
    },
    content: `# Long Book

## Table of Contents

- Part One
- Part Two

## Extracted Markdown

## Table of Contents

- Preface

## Copyright Information

Publisher: Example

## Part One

${"A".repeat(5000)}

## Part Two

${"B".repeat(5000)}
`
  };

  const digest = buildEpubCompileDigest(rawNote, {
    maxChars: 1600,
    minExcerptChars: 120,
    maxExcerptChars: 200
  });

  assert.ok(digest.length <= 1600);
  assert.match(digest, /## Compile Digest/);
  assert.doesNotMatch(digest, /### Table of Contents/);
  assert.doesNotMatch(digest, /### Copyright Information/);
  assert.match(digest, /### Part One/);
  assert.match(digest, /### Part Two/);
  assert.match(digest, /\[Excerpt truncated\]/);

  const variants = buildEpubCompilePromptVariants(rawNote, {
    maxCharsVariants: [12000, 8000, 6000]
  });
  assert.deepEqual(
    variants.map((variant) => variant.label),
    ["epub-digest-12000", "epub-digest-8000", "epub-digest-6000"]
  );
  assert.ok(variants[0].promptContent.length > variants[1].promptContent.length);
  assert.ok(variants[1].promptContent.length > variants[2].promptContent.length);
});
