import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import test from "node:test";
import {
  deduplicateEpubArtifacts,
  importEpubLibrary,
  loadEpubArtifacts
} from "../src/epub-library.mjs";
import { parseFrontmatter, validateRawFrontmatter } from "../src/frontmatter.mjs";

test("loadEpubArtifacts normalizes external epub files without copying them", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-epub-library-"));

  try {
    const rootPath = path.join(tempRoot, "books");
    const filePath = path.join(rootPath, "Test.Book.epub");
    fs.mkdirSync(rootPath, { recursive: true });
    fs.writeFileSync(filePath, "dummy-epub", "utf8");

    const [artifact] = loadEpubArtifacts([filePath], {
      roots: [rootPath],
      machineRoot: "08-ai-kb"
    });

    assert.equal(artifact.title, "Test Book");
    assert.equal(artifact.relativePath, "Test.Book.epub");
    assert.match(artifact.filenameBase, /^Test-Book--[a-f0-9]{8}$/);
    assert.equal(artifact.notePath.startsWith("08-ai-kb/10-raw/books/"), true);
    assert.match(artifact.sourceUrl, /^file:/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("importEpubLibrary writes lightweight book index notes and leaves binaries outside the vault", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-epub-import-"));

  try {
    const externalRoot = path.join(tempRoot, "external-books");
    const filePath = path.join(externalRoot, "Deep.Work.epub");
    fs.mkdirSync(externalRoot, { recursive: true });
    fs.writeFileSync(filePath, "dummy-epub", "utf8");

    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };

    const [artifact] = loadEpubArtifacts([filePath], {
      roots: [externalRoot],
      machineRoot: config.machineRoot
    });
    const deduped = deduplicateEpubArtifacts([artifact, artifact]);
    assert.equal(deduped.length, 1);

    const [result] = importEpubLibrary(config, deduped, {
      status: "archived",
      preferCli: false,
      allowFilesystemFallback: true
    });

    assert.match(result.path, /^08-ai-kb\/10-raw\/books\/Deep-Work-[a-f0-9]{8}\.md$/);

    const content = fs.readFileSync(path.join(config.vaultPath, result.path), "utf8");
    const frontmatter = parseFrontmatter(content);
    assert.doesNotThrow(() => validateRawFrontmatter(frontmatter));
    assert.equal(frontmatter.source_type, "epub");
    assert.equal(frontmatter.status, "archived");
    assert.match(content, /Indexed from an external EPUB library/);
    assert.match(content, /Local path:/);
    assert.match(content, /Open EPUB/);

    const copiedBinaries = [];
    walkFiles(config.vaultPath, copiedBinaries);
    assert.equal(copiedBinaries.some((entry) => entry.endsWith(".epub")), false);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

function walkFiles(directory, results) {
  let entries = [];
  try {
    entries = fs.readdirSync(directory, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      walkFiles(fullPath, results);
      continue;
    }

    if (entry.isFile()) {
      results.push(fullPath);
    }
  }
}
