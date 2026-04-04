import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { tmpdir } from "node:os";
import {
  deduplicateArticleArtifacts,
  formatArticleCorpusBody,
  importArticleCorpus,
  isLikelyFixtureArticleArtifactPath,
  loadArticleArtifacts
} from "../src/article-corpus.mjs";
import {
  deduplicateEpubArtifacts,
  importEpubLibrary,
  loadEpubArtifacts
} from "../src/epub-library.mjs";
import { assertWithinBoundary } from "../src/boundary.mjs";
import { buildBootstrapPlan } from "../src/bootstrap-plan.mjs";
import { executeCompileForRawNote } from "../src/compile-runner.mjs";
import {
  applyCompileOutput,
  buildCompilePrompt,
  buildHealthCheckReport
} from "../src/compile-pipeline.mjs";
import { loadConfig } from "../src/config.mjs";
import {
  loadCodexLlmProvider,
  parseTomlConfig
} from "../src/codex-config.mjs";
import { findExistingByDedupKey, generateDedupKey } from "../src/dedup.mjs";
import {
  generateFrontmatter,
  parseFrontmatter,
  validateRawFrontmatter,
  validateWikiFrontmatter
} from "../src/frontmatter.mjs";
import {
  extractHumanOverrides,
  hasHumanOverrides,
  mergeWithOverrides
} from "../src/human-override.mjs";
import { ingestRawNote, sanitizeFilename } from "../src/ingest.mjs";
import {
  buildResponseEndpointCandidates,
  callResponsesApi,
  extractResponseOutputText
} from "../src/llm-provider.mjs";
import {
  applyRelatedSection,
  buildRelatedGraph,
  collectLinkableNotes,
  rebuildAutomaticLinks
} from "../src/link-graph.mjs";
import { buildObsidianArgs, resolveObsidianEnvironment } from "../src/obsidian-cli.mjs";
import {
  collectRollbackCandidates,
  executeRollback,
  writeRollbackLog
} from "../src/rollback.mjs";

const pendingRuns = [];

function run(name, fn) {
  try {
    const result = fn();
    if (result && typeof result.then === "function") {
      pendingRuns.push(
        result
          .then(() => {
            console.log(`[PASS] ${name}`);
          })
          .catch((error) => {
            console.error(`[FAIL] ${name}`);
            console.error(error.stack || String(error));
            process.exitCode = 1;
          })
      );
      return;
    }

    console.log(`[PASS] ${name}`);
  } catch (error) {
    console.error(`[FAIL] ${name}`);
    console.error(error.stack || String(error));
    process.exitCode = 1;
  }
}

run("loadConfig returns required fields", () => {
  const config = loadConfig();
  assert.equal(typeof config.vaultPath, "string");
  assert.equal(typeof config.vaultName, "string");
  assert.equal(typeof config.machineRoot, "string");
  assert.ok(Array.isArray(config.obsidian.cliCandidates));
  assert.ok(Array.isArray(config.obsidian.exeCandidates));
});

run("bootstrap plan stays within machine root", () => {
  const config = loadConfig();
  const plan = buildBootstrapPlan(config);

  for (const dir of plan.directories) {
    assert.doesNotThrow(
      () => assertWithinBoundary(dir, config.machineRoot),
      `Directory escaped root: ${dir}`
    );
  }

  for (const note of plan.notes) {
    assert.doesNotThrow(
      () => assertWithinBoundary(note.path, config.machineRoot),
      `Note escaped root: ${note.path}`
    );
    assert.equal(typeof note.content, "string");
    assert.ok(note.content.length > 0);
  }
});

run("vault selector is prepended first", () => {
  const config = loadConfig();
  const args = buildObsidianArgs(config, ["read", "path=README.md"]);
  assert.equal(args[0], `vault=${config.vaultName}`);
  assert.equal(args[1], "read");
});

run("resolveObsidianEnvironment prefers registered command when available", () => {
  const env = resolveObsidianEnvironment(
    {
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: ["C:\\Obsidian\\Obsidian.exe"]
      }
    },
    {
      commandExists(command) {
        return command === "obsidian";
      },
      pathExists(candidate) {
        return candidate === "C:\\Obsidian\\Obsidian.exe";
      }
    }
  );

  assert.equal(env.cliCommand, "obsidian");
  assert.equal(env.cliMode, "registered-command");
  assert.equal(env.exePath, "C:\\Obsidian\\Obsidian.exe");
});

run("resolveObsidianEnvironment falls back to configured desktop executable", () => {
  const env = resolveObsidianEnvironment(
    {
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: ["C:\\Obsidian\\Obsidian.exe"]
      }
    },
    {
      commandExists() {
        return false;
      },
      pathExists(candidate) {
        return candidate === "C:\\Obsidian\\Obsidian.exe";
      }
    }
  );

  assert.equal(env.cliCommand, "C:\\Obsidian\\Obsidian.exe");
  assert.equal(env.cliMode, "desktop-executable");
  assert.equal(env.exePath, "C:\\Obsidian\\Obsidian.exe");
});

run("resolveObsidianEnvironment infers executable from PATH hint", () => {
  const inferredPath = "C:\\Users\\rickylu\\AppData\\Local\\Programs\\obsidian\\Obsidian.exe";
  const env = resolveObsidianEnvironment(
    {
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: []
      }
    },
    {
      env: {
        Path: "C:\\WINDOWS\\system32;C:\\Users\\rickylu\\AppData\\Local\\Programs\\obsidian"
      },
      commandExists() {
        return false;
      },
      pathExists(candidate) {
        return candidate === inferredPath;
      }
    }
  );

  assert.equal(env.cliCommand, inferredPath);
  assert.equal(env.cliMode, "desktop-executable");
  assert.equal(env.exePath, inferredPath);
});

run("frontmatter generation uses v2 fields", () => {
  const raw = generateFrontmatter("raw", {
    source_type: "manual",
    topic: "test",
    source_url: "https://example.com"
  });
  const wiki = generateFrontmatter("wiki", {
    topic: "test",
    dedup_key: "test::concept"
  });

  assert.match(raw, /captured_at: "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00"/);
  assert.match(raw, /kb_date: "\d{4}-\d{2}-\d{2}"/);
  assert.match(wiki, /kb_source_count: 0/);
  assert.match(wiki, /dedup_key: "test::concept"/);
});

run("bootstrap plan notes with kb_type also have kb_date", () => {
  const config = loadConfig();
  const plan = buildBootstrapPlan(config);

  for (const note of plan.notes) {
    if (note.content.startsWith("---") && note.content.includes("kb_type:")) {
      assert.ok(note.content.includes("kb_date:"), `Missing kb_date in ${note.path}`);
    }
  }

  assert.ok(
    plan.directories.includes(`${config.machineRoot}/90-ops/prompts`),
    "Missing 90-ops/prompts directory"
  );

  const notePaths = plan.notes.map((note) => note.path);
  assert.ok(
    notePaths.includes(`${config.machineRoot}/30-views/01-Stale Notes.md`),
    "Missing stale notes view"
  );
  assert.ok(
    notePaths.includes(`${config.machineRoot}/30-views/02-Open Questions.md`),
    "Missing open questions view"
  );
  assert.ok(
    notePaths.includes(`${config.machineRoot}/30-views/03-Sources by Topic.md`),
    "Missing sources by topic view"
  );

  const dashboardNote = plan.notes.find(
    (note) => note.path === `${config.machineRoot}/30-views/00-KB Dashboard.md`
  );
  assert.ok(dashboardNote);
  assert.match(dashboardNote.content, /SORT kb_date DESC/);
  assert.match(dashboardNote.content, /## Stats/);

  const kbHomeNote = plan.notes.find(
    (note) => note.path.endsWith("/KB Home.md")
  );
  assert.ok(kbHomeNote);
  assert.match(kbHomeNote.content, /01-Stale Notes/);
});

run("dedup key generation and missing lookup stay normalized", () => {
  const key = generateDedupKey("Topic", "Concept", "HTTPS://EXAMPLE.COM");
  assert.equal(key, "topic::concept::https://example.com");
  assert.equal(findExistingByDedupKey("C:/definitely/missing", "08-ai-kb", key), null);
});

run("human override helpers preserve manual content", () => {
  const existing = `# Old

<!-- human-override -->
Keep me
<!-- /human-override -->`;

  const overrides = extractHumanOverrides(existing);
  assert.equal(overrides.length, 1);
  assert.equal(hasHumanOverrides(existing), true);

  const merged = mergeWithOverrides("# New\n\nBody", overrides);
  assert.match(merged, /Keep me/);
});

run("ingest filename sanitization is deterministic", () => {
  assert.equal(
    sanitizeFilename('  Article: "CLI/Obsidian" <Draft>?  '),
    "Article-CLIObsidian-Draft"
  );
  assert.equal(sanitizeFilename('<<>>:"/\\\\|?*'), "untitled-note");
});

run("raw frontmatter accepts epub source_type", () => {
  assert.doesNotThrow(() =>
    validateRawFrontmatter({
      kb_type: "raw",
      source_type: "epub",
      topic: "Deep Work",
      source_url: "file:///D:/books/deep-work.epub",
      captured_at: "2026-04-04T10:00:00+08:00",
      kb_date: "2026-04-04",
      status: "archived",
      managed_by: "human"
    })
  );
});

run("article corpus fixture filter catches replay and placeholder artifacts", () => {
  assert.equal(
    isLikelyFixtureArticleArtifactPath(
      "C:/tmp/claude-code-article-resume-placeholder-diagnostic/workflow/publish-package.json"
    ),
    true
  );
  assert.equal(
    isLikelyFixtureArticleArtifactPath(
      "C:/tmp/claude-code-secret-features/workflow-rerun-headline-traffic/publish-package.json"
    ),
    true
  );
  assert.equal(
    isLikelyFixtureArticleArtifactPath(
      "C:/tmp/live-ai-learning-article/run/article-publish-result.json"
    ),
    false
  );
});

run("ingest raw note writes valid frontmatter into lane", () => {
  const tempVault = fs.mkdtempSync(path.join(process.cwd(), ".tmp-ingest-run-tests-"));

  try {
    const result = ingestRawNote(
      {
        vaultPath: tempVault,
        vaultName: "Test Vault",
        machineRoot: "08-ai-kb",
        obsidian: {
          cliCandidates: [],
          exeCandidates: []
        }
      },
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

    const content = fs.readFileSync(path.join(tempVault, result.path), "utf8");
    const frontmatter = parseFrontmatter(content);

    assert.ok(frontmatter);
    assert.doesNotThrow(() => validateRawFrontmatter(frontmatter));
  } finally {
    fs.rmSync(tempVault, { recursive: true, force: true });
  }
});

run("ingest raw note supports epub books lane and stable filename base", () => {
  const tempVault = fs.mkdtempSync(path.join(process.cwd(), ".tmp-ingest-epub-run-tests-"));

  try {
    const result = ingestRawNote(
      {
        vaultPath: tempVault,
        vaultName: "Test Vault",
        machineRoot: "08-ai-kb",
        obsidian: {
          cliCandidates: [],
          exeCandidates: []
        }
      },
      {
        sourceType: "epub",
        topic: "Deep Work",
        sourceUrl: "file:///D:/books/deep-work.epub",
        title: "Deep Work",
        filenameBase: "Deep-Work--abc12345",
        body: "External epub index entry.",
        status: "archived"
      },
      {
        preferCli: false,
        allowFilesystemFallback: true
      }
    );

    assert.equal(result.path, "08-ai-kb/10-raw/books/Deep-Work-abc12345.md");
    const content = fs.readFileSync(path.join(tempVault, result.path), "utf8");
    const frontmatter = parseFrontmatter(content);
    assert.equal(frontmatter.source_type, "epub");
    assert.equal(frontmatter.status, "archived");
  } finally {
    fs.rmSync(tempVault, { recursive: true, force: true });
  }
});

run("article corpus loader normalizes publish results", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-article-corpus-run-tests-"));

  try {
    const artifactPath = path.join(tempRoot, "article-publish-result.json");
    fs.writeFileSync(
      artifactPath,
      JSON.stringify(
        {
          analysis_time: "2026-04-04T10:00:00+08:00",
          publication_readiness: "ready",
          review_gate: { status: "approved" },
          selected_topic: {
            title: "Claude Code Hidden Features",
            summary: "Workflow summary",
            keywords: ["Claude Code", "Agent"],
            source_items: [
              {
                source_name: "X post",
                source_type: "social",
                summary: "Social trigger",
                url: "https://x.com/example/status/1"
              }
            ]
          },
          publish_package: {
            title: "Claude Code Hidden Features",
            digest: "Digest text",
            keywords: ["Codex", "Claude Code"],
            content_markdown: "# Claude Code Hidden Features\n\nBody copy."
          },
          workflow_stage: {
            result_path: ".tmp/example/workflow-result.json"
          }
        },
        null,
        2
      ),
      "utf8"
    );

    const [artifact] = loadArticleArtifacts(artifactPath, {
      workspaceRoot: tempRoot
    });

    assert.equal(artifact.title, "Claude Code Hidden Features");
    assert.equal(artifact.reviewStatus, "approved");
    assert.match(artifact.contentMarkdown, /Body copy\./);
    assert.deepEqual(artifact.keywords, ["Codex", "Claude Code", "Agent"]);
    assert.equal(artifact.sourceItems.length, 1);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("article corpus dedup keeps newest artifact", () => {
  const deduped = deduplicateArticleArtifacts([
    { title: "Same Title", analysisTimestamp: 10 },
    { title: "Same Title", analysisTimestamp: 20 },
    { title: "Different Title", analysisTimestamp: 15 }
  ]);

  assert.equal(deduped.length, 2);
  assert.equal(deduped[0].analysisTimestamp, 20);
});

run("article corpus import writes dedicated article lane notes", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-article-import-run-tests-"));

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

    const [result] = importArticleCorpus(
      config,
      [
        {
          title: "Claude Code Hidden Features",
          topic: "Claude Code Hidden Features",
          analysisTime: "2026-04-04T10:00:00+08:00",
          sourceUrl: "workflow://article-corpus/claude-code-hidden-features",
          digest: "Digest text",
          keywords: ["Claude Code"],
          contentMarkdown: "# Claude Code Hidden Features\n\nBody copy.",
          publicationReadiness: "ready",
          reviewStatus: "approved",
          artifactPath: "C:/tmp/article-publish-result.json",
          publishPackagePath: "C:/tmp/publish-package.json",
          workflowResultPath: "C:/tmp/workflow-result.json",
          feedbackPath: "C:/tmp/ARTICLE-FEEDBACK.md",
          sourceItems: [
            {
              sourceName: "X post",
              sourceType: "social",
              summary: "Social trigger",
              url: "https://x.com/example/status/1"
            }
          ]
        }
      ],
      {
        preferCli: false,
        allowFilesystemFallback: true
      }
    );

    const content = fs.readFileSync(path.join(tempRoot, result.path), "utf8");
    const frontmatter = parseFrontmatter(content);
    assert.equal(result.path, "08-ai-kb/10-raw/articles/Claude-Code-Hidden-Features.md");
    assert.doesNotThrow(() => validateRawFrontmatter(frontmatter));
    assert.equal(frontmatter.source_type, "article");
    assert.match(content, /## Corpus Metadata/);
    assert.match(content, /## Article Markdown/);
    assert.match(content, /Body copy\./);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("article corpus formatter strips duplicate leading title headings", () => {
  const body = formatArticleCorpusBody({
    title: "Claude Code Hidden Features",
    topic: "Claude Code Hidden Features",
    analysisTime: "2026-04-04T10:00:00+08:00",
    publicationReadiness: "ready",
    reviewStatus: "approved",
    artifactPath: "C:/tmp/article-publish-result.json",
    publishPackagePath: "",
    workflowResultPath: "",
    feedbackPath: "",
    digest: "",
    keywords: [],
    sourceItems: [],
    contentMarkdown: "# Claude Code Hidden Features\n\nBody copy."
  });

  assert.doesNotMatch(body, /^# Claude Code Hidden Features/m);
  assert.match(body, /Body copy\./);
});

run("epub library loader normalizes external files without copying them", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-epub-library-run-tests-"));

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

run("epub library import writes lightweight index notes and keeps binaries outside the vault", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-epub-import-run-tests-"));

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
    assert.equal(frontmatter.source_type, "epub");
    assert.equal(frontmatter.status, "archived");
    assert.match(content, /Indexed from an external EPUB library/);

    const copiedBinaries = [];
    walkFiles(config.vaultPath, copiedBinaries);
    assert.equal(copiedBinaries.some((entry) => entry.endsWith(".epub")), false);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("compile prompt injects raw content and topic context", () => {
  const prompt = buildCompilePrompt(
    "RAW={{RAW_CONTENT}}\nTOPIC={{TOPIC}}\nNOTES={{EXISTING_NOTES}}",
    {
      content: "---\nkb_type: raw\n---\n\n# Raw",
      frontmatter: {
        topic: "LLM Knowledge Bases"
      }
    },
    [
      {
        title: "Source Overview",
        relativePath: "08-ai-kb/20-wiki/sources/Source-Overview.md",
        frontmatter: {
          wiki_kind: "source",
          compiled_from: ["08-ai-kb/10-raw/web/one.md"]
        }
      }
    ]
  );

  assert.match(prompt, /TOPIC=LLM Knowledge Bases/);
  assert.match(prompt, /Source Overview \(source\)/);
});

run("compile output writes wiki notes, updates raw status, and logs", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-compile-run-tests-"));

  try {
    const { config, rawPath } = createCompileFixture(tempRoot);
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
          }
        ]
      },
      {
        timestamp: "2026-04-04T12:00:00+08:00",
        preferCli: false,
        allowFilesystemFallback: true
      }
    );

    assert.equal(result.rawStatus, "compiled");
    assert.equal(result.results.length, 1);
    assert.ok(fs.existsSync(result.logFile));

    const rawContent = fs.readFileSync(path.join(config.vaultPath, rawPath), "utf8");
    const rawFrontmatter = parseFrontmatter(rawContent);
    assert.doesNotThrow(() => validateRawFrontmatter(rawFrontmatter));
    assert.equal(rawFrontmatter.status, "compiled");

    const wikiContent = fs.readFileSync(
      path.join(config.vaultPath, config.machineRoot, "20-wiki", "sources", "Karpathy-Source.md"),
      "utf8"
    );
    assert.doesNotThrow(() => validateWikiFrontmatter(parseFrontmatter(wikiContent)));
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("health check reports missing sources and dedup conflicts", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-health-run-tests-"));

  try {
    const { config, rawPath } = createCompileFixture(tempRoot);
    const wikiRoot = path.join(config.vaultPath, config.machineRoot, "20-wiki", "sources");
    fs.mkdirSync(wikiRoot, { recursive: true });

    fs.writeFileSync(
      path.join(wikiRoot, "First.md"),
      buildWikiFixture({
        wiki_kind: "source",
        topic: "LLM Knowledge Bases",
        compiled_from: [rawPath],
        compiled_at: "2026-04-03T12:00:00+08:00",
        kb_date: "2026-04-03",
        kb_source_count: 1,
        dedup_key: "llm knowledge bases::source::https://example.com/article",
        title: "First",
        body: "## Summary\n\nFirst."
      }),
      "utf8"
    );

    fs.writeFileSync(
      path.join(wikiRoot, "Second.md"),
      buildWikiFixture({
        wiki_kind: "source",
        topic: "LLM Knowledge Bases",
        compiled_from: ["08-ai-kb/10-raw/web/missing.md"],
        compiled_at: "2026-04-04T11:00:00+08:00",
        kb_date: "2026-04-04",
        kb_source_count: 1,
        dedup_key: "llm knowledge bases::source::https://example.com/article",
        title: "Second",
        body: "## Summary\n\nSecond."
      }),
      "utf8"
    );

    const { report } = buildHealthCheckReport(config);
    assert.equal(report.missing_source.length, 1);
    assert.equal(report.dedup_conflicts.length, 1);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("link graph relates notes that mention each other or share topic", () => {
  const graph = buildRelatedGraph(
    [
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
    ],
    {
      maxLinks: 8,
      minScore: 4
    }
  );

  assert.equal(graph.get("08-ai-kb/20-wiki/concepts/Claude-Code.md").length, 1);
  assert.equal(
    graph.get("08-ai-kb/10-raw/articles/Claude-Code-Hidden-Features.md").length,
    1
  );
});

run("link graph ignores shared template headings across unrelated raw notes", () => {
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

  assert.equal(graph.get("08-ai-kb/10-raw/books/Deep-Work.md").length, 0);
  assert.equal(graph.get("08-ai-kb/10-raw/books/Monetary-History.md").length, 0);
});

run("link graph managed block replacement stays idempotent", () => {
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

run("rollback only targets codex-managed notes and preserves human notes", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-rollback-run-tests-"));

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

run("link graph rebuild updates wiki and article notes in the vault", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-link-graph-run-tests-"));

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

run("collectLinkableNotes includes epub raw notes from the books lane", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-link-graph-epub-run-tests-"));

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

run("codex config parser loads custom provider and auth", () => {
  const codexHome = fs.mkdtempSync(path.join(tmpdir(), "obsidian-kb-codex-home-"));

  try {
    fs.writeFileSync(
      path.join(codexHome, "config.toml"),
      `model_provider = "custom"
model = "gpt-5.4"
model_reasoning_effort = "xhigh"
disable_response_storage = true

[model_providers.custom]
wire_api = "responses"
requires_openai_auth = true
base_url = "https://ice.v.ua"
`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(codexHome, "auth.json"),
      JSON.stringify({ OPENAI_API_KEY: "sk-test-value" }),
      "utf8"
    );

    const provider = loadCodexLlmProvider({
      env: {
        CODEX_HOME: codexHome
      }
    });

    assert.equal(provider.providerName, "custom");
    assert.equal(provider.model, "gpt-5.4");
    assert.equal(provider.baseUrl, "https://ice.v.ua");
    assert.equal(provider.wireApi, "responses");
    assert.equal(provider.reasoningEffort, "xhigh");
    assert.equal(provider.apiKey, "sk-test-value");
  } finally {
    fs.rmSync(codexHome, { recursive: true, force: true });
  }
});

run("codex config falls back to official OpenAI defaults when no custom provider is set", () => {
  const codexHome = fs.mkdtempSync(path.join(tmpdir(), "obsidian-kb-openai-home-"));

  try {
    fs.writeFileSync(
      path.join(codexHome, "config.toml"),
      `model = "gpt-5.4"
disable_response_storage = true
`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(codexHome, "auth.json"),
      JSON.stringify({ OPENAI_API_KEY: "sk-official" }),
      "utf8"
    );

    const provider = loadCodexLlmProvider({
      env: {
        CODEX_HOME: codexHome
      }
    });

    assert.equal(provider.providerName, "openai");
    assert.equal(provider.baseUrl, "https://api.openai.com/v1");
    assert.equal(provider.apiKey, "sk-official");
  } finally {
    fs.rmSync(codexHome, { recursive: true, force: true });
  }
});

run("mini TOML parser keeps nested sections and arrays", () => {
  const parsed = parseTomlConfig(`
[model_providers.custom]
wire_api = "responses"
args = ["/c", "npx", "-y"]
`);

  assert.equal(parsed.model_providers.custom.wire_api, "responses");
  assert.deepEqual(parsed.model_providers.custom.args, ["/c", "npx", "-y"]);
});

run("response endpoint builder adds a v1 fallback for custom roots", () => {
  assert.deepEqual(buildResponseEndpointCandidates("https://ice.v.ua", "responses"), [
    "https://ice.v.ua/responses",
    "https://ice.v.ua/v1/responses"
  ]);
  assert.deepEqual(buildResponseEndpointCandidates("https://api.openai.com/v1", "responses"), [
    "https://api.openai.com/v1/responses"
  ]);
});

run("responses output extractor supports both output_text and nested content blocks", () => {
  assert.equal(extractResponseOutputText({ output_text: "[{\"title\":\"One\"}]" }), "[{\"title\":\"One\"}]");
  assert.equal(
    extractResponseOutputText({
      output: [
        {
          content: [
            {
              type: "output_text",
              text: "[{\"title\":\"Two\"}]"
            }
          ]
        }
      ]
    }),
    "[{\"title\":\"Two\"}]"
  );
});

run("responses caller retries /v1 fallback after a 404 and preserves auth header", async () => {
  const calls = [];
  const provider = {
    providerName: "custom",
    model: "gpt-5.4",
    baseUrl: "https://ice.v.ua",
    wireApi: "responses",
    apiKey: "sk-test"
  };

  const result = await callResponsesApi(provider, "Compile this note", {
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      if (calls.length === 1) {
        return {
          ok: false,
          status: 404,
          text: async () => "not found"
        };
      }

      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ output_text: "[{\"wiki_kind\":\"source\",\"title\":\"OK\",\"body\":\"Body\"}]" })
      };
    }
  });

  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, "https://ice.v.ua/responses");
  assert.equal(calls[1].url, "https://ice.v.ua/v1/responses");
  assert.equal(calls[1].init.headers.authorization, "Bearer sk-test");
  assert.equal(result.endpoint, "https://ice.v.ua/v1/responses");
});

run("compile execution marks the raw note as error when provider execution fails", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-compile-runner-error-"));

  try {
    const { config, rawPath } = createCompileFixture(tempRoot);
    const rawContent = fs.readFileSync(path.join(config.vaultPath, rawPath), "utf8");
    const rawNote = {
      content: rawContent,
      frontmatter: parseFrontmatter(rawContent),
      relativePath: rawPath,
      title: "karpathy-article"
    };

    const result = await executeCompileForRawNote(
      config,
      {
        rawNote,
        existingWikiNotes: [],
        templateContent: "RAW={{RAW_CONTENT}}\nTOPIC={{TOPIC}}",
        provider: {
          providerName: "custom",
          model: "gpt-5.4",
          baseUrl: "https://ice.v.ua",
          wireApi: "responses",
          apiKey: "sk-test"
        }
      },
      {
        preferCli: false,
        allowFilesystemFallback: true,
        timestamp: "2026-04-04T20:30:00+08:00",
        fetchImpl: async () => {
          throw new Error("network unavailable");
        }
      }
    );

    assert.equal(result.ok, false);
    const updatedRawFrontmatter = parseFrontmatter(
      fs.readFileSync(path.join(config.vaultPath, rawPath), "utf8")
    );
    assert.equal(updatedRawFrontmatter.status, "error");
    assert.ok(fs.existsSync(result.logFile));
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

if (process.exitCode) {
  process.exit(process.exitCode);
}

function createCompileFixture(tempRoot) {
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

  fs.writeFileSync(path.join(vaultPath, machineRoot, "20-wiki", "README.md"), "# README\n", "utf8");

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

await Promise.allSettled(pendingRuns);

if (process.exitCode) {
  process.exit(process.exitCode);
}
