import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import test from "node:test";
import {
  deduplicateArticleArtifacts,
  formatArticleCorpusBody,
  importArticleCorpus,
  isLikelyFixtureArticleArtifactPath,
  loadArticleArtifacts
} from "../src/article-corpus.mjs";
import { parseFrontmatter, validateRawFrontmatter } from "../src/frontmatter.mjs";

test("loadArticleArtifacts normalizes article publish results", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-article-corpus-"));

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
    assert.equal(artifact.topic, "Claude Code Hidden Features");
    assert.equal(artifact.publicationReadiness, "ready");
    assert.equal(artifact.reviewStatus, "approved");
    assert.match(artifact.contentMarkdown, /Body copy\./);
    assert.deepEqual(artifact.keywords, ["Codex", "Claude Code", "Agent"]);
    assert.equal(artifact.sourceItems.length, 1);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("deduplicateArticleArtifacts keeps the newest artifact for a title", () => {
  const deduped = deduplicateArticleArtifacts([
    {
      title: "Same Title",
      analysisTimestamp: 10
    },
    {
      title: "Same Title",
      analysisTimestamp: 20
    },
    {
      title: "Different Title",
      analysisTimestamp: 15
    }
  ]);

  assert.equal(deduped.length, 2);
  assert.equal(deduped[0].analysisTimestamp, 20);
});

test("importArticleCorpus writes article notes into the dedicated lane", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-article-import-"));

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

    assert.equal(result.path, "08-ai-kb/10-raw/articles/Claude-Code-Hidden-Features.md");

    const content = fs.readFileSync(path.join(tempRoot, result.path), "utf8");
    const frontmatter = parseFrontmatter(content);
    assert.doesNotThrow(() => validateRawFrontmatter(frontmatter));
    assert.equal(frontmatter.source_type, "article");
    assert.match(content, /## Corpus Metadata/);
    assert.match(content, /## Article Markdown/);
    assert.match(content, /Body copy\./);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("formatArticleCorpusBody strips duplicate leading title headings", () => {
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

test("isLikelyFixtureArticleArtifactPath catches placeholder and replay artifacts", () => {
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
