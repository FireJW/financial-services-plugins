import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { generateFrontmatter } from "../src/frontmatter.mjs";
import {
  buildGraphifySidecarReadme,
  buildGraphifyTopicPaths,
  buildGraphifyVaultNote,
  resetGraphifyTopicWorkspace,
  scoreTopicSearchNote,
  stageGraphifyTopicCorpus
} from "../src/graphify-sidecar.mjs";
import {
  buildGraphActivationTraceNote,
  buildGraphNetworkIndexNote,
  buildSourceFileToVaultPathMap
} from "../src/graphify-network-index.mjs";
import {
  buildGraphContract,
  buildGraphContractMarkdown,
  lintGraphArtifacts,
  writeGraphContractArtifacts
} from "../src/graphify-contract.mjs";
import {
  discoverGraphifyTopicWorkspaces,
  normalizeGraphifyTopicLabel,
  readGraphifyWorkspaceStatus
} from "../src/graphify-topic-workspaces.mjs";
import {
  buildGraphifyRefreshRequest,
  runGraphifyTopicRefresh
} from "../src/graphify-refresh.mjs";

test("graphify sidecar stages exact and profile fallback topic notes", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-focused-"));
  try {
    const config = createConfig(tempRoot);
    writeRawNote(config, "web/Karpathy.md", {
      topic: "LLM Knowledge Bases",
      status: "queued",
      body: "LLM wiki workflow notes."
    });
    writeWikiNote(config, "sources/Karpathy-Source.md", {
      kind: "source",
      topic: "LLM Knowledge Bases",
      title: "Karpathy Source",
      body: "A source summary."
    });

    const exact = stageGraphifyTopicCorpus(config, "LLM Knowledge Bases");
    assert.equal(exact.staged.counts.raw, 1);
    assert.equal(exact.staged.counts.wiki, 1);
    assert.ok(fs.existsSync(exact.paths.manifestPath));
    assert.match(buildGraphifySidecarReadme(exact.staged, exact.paths), /Suggested command/);
    assert.match(buildGraphifyVaultNote(config, "LLM Knowledge Bases", exact.paths).path, /07-Graph Insights/);

    writeRawNote(config, "books/Momentum-Playbook.md", {
      topic: "Breakout Trend Following",
      status: "compiled",
      sourceType: "epub",
      body: "Momentum trading focuses on breakout continuation and trend strength."
    });
    writeWikiNote(config, "concepts/Momentum-Concept.md", {
      kind: "concept",
      topic: "Breakout Trend Following",
      title: "Momentum Concept",
      body: "Momentum trading combines relative strength, breakout confirmation, and risk control."
    });

    const fallback = stageGraphifyTopicCorpus(config, "momentum trading");
    assert.equal(fallback.staged.selectionMode, "profile-whitelist");
    assert.equal(fallback.staged.fallbackProfileId, "momentum-trading");
    assert.equal(fallback.staged.counts.raw, 1);
    assert.equal(fallback.staged.counts.wiki, 1);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("graphify scoring, reset, and workspace status cover topic maintenance", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-status-"));
  try {
    const scored = scoreTopicSearchNote(
      {
        title: "Momentum Trading Breakouts",
        relativePath: "08-ai-kb/10-raw/books/Momentum-Trading.md",
        content: "Momentum trading setups and breakout entries.",
        frontmatter: { topic: "breakout trend trading" }
      },
      "momentum trading"
    );
    assert.ok(scored.score > 0);
    assert.deepEqual(scored.matchedTokens.sort(), ["momentum", "trading"]);

    assert.equal(
      scoreTopicSearchNote(
        {
          title: "21st Century Monetary Policy",
          relativePath: "08-ai-kb/10-raw/books/Policy.md",
          content: "Inflation expectations developed momentum.",
          frontmatter: { topic: "Federal Reserve inflation history" }
        },
        "momentum trading"
      ).score,
      0
    );

    const paths = buildGraphifyTopicPaths(tempRoot, "Momentum Trading");
    fs.mkdirSync(paths.rawRoot, { recursive: true });
    fs.mkdirSync(paths.wikiRoot, { recursive: true });
    fs.writeFileSync(path.join(paths.rawRoot, "stale.md"), "stale", "utf8");
    resetGraphifyTopicWorkspace(paths);
    assert.equal(fs.existsSync(path.join(paths.rawRoot, "stale.md")), false);

    const root = path.join(tempRoot, "graphify-sidecar", "CAN-SLIM");
    fs.mkdirSync(path.join(root, "graphify-out"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "manifest.json"),
      JSON.stringify({ topic: "CAN SLIM", slug: "CAN-SLIM", selectionMode: "profile-whitelist" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(root, "graphify-out", "graph-contract.json"),
      JSON.stringify({ graphCounts: { nodes: 2, edges: 1, communities: 1 } }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(root, "graphify-out", "graph-lint.json"),
      JSON.stringify({ status: "pass", warningCount: 0, errorCount: 0, issues: [] }),
      "utf8"
    );
    fs.writeFileSync(path.join(root, "graphify-out", "graph.json"), "{}", "utf8");

    const workspaces = discoverGraphifyTopicWorkspaces(tempRoot);
    assert.equal(workspaces.length, 1);
    assert.equal(normalizeGraphifyTopicLabel('"', "fallback"), "fallback");
    assert.equal(readGraphifyWorkspaceStatus(workspaces[0]).status, "pass");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("graphify contract and network notes summarize graph artifacts", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-contract-focused-"));
  try {
    const config = createConfig(tempRoot);
    const paths = buildGraphifyTopicPaths(tempRoot, "Wyckoff");
    fs.mkdirSync(paths.graphifyOutRoot, { recursive: true });
    fs.writeFileSync(
      paths.manifestPath,
      JSON.stringify({
        topic: "Wyckoff",
        selectionMode: "profile-whitelist",
        rawNotes: [{ relativePath: "08-ai-kb/10-raw/books/Wyckoff-Book.md" }],
        wikiNotes: [{ relativePath: "08-ai-kb/20-wiki/concepts/Wyckoff-methodology.md", wikiKind: "concept" }]
      }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(paths.graphifyOutRoot, "graph.json"),
      JSON.stringify({
        nodes: [
          { id: "raw_book", label: "Wyckoff Book", source_file: "raw/Wyckoff-Book.md", community: 0 },
          { id: "wiki_method", label: "Wyckoff methodology", source_file: "wiki/concept/Wyckoff-methodology.md", community: 1 }
        ],
        links: [
          { source: "raw_book", target: "wiki_method", relation: "conceptually_related_to", confidence_score: 0.82 }
        ]
      }),
      "utf8"
    );
    fs.writeFileSync(path.join(paths.graphifyOutRoot, "markdown-extraction.json"), "{}", "utf8");

    const contract = buildGraphContract(paths);
    assert.equal(contract.graphCounts.nodes, 2);
    assert.equal(contract.manifestCoverage.missingStagedFiles.length, 0);
    assert.match(buildGraphContractMarkdown(paths, { contract, lint: lintGraphArtifacts(paths, { contract }) }), /query-wiki\.mjs/);
    assert.equal(fs.existsSync(writeGraphContractArtifacts(paths, { contract, lint: lintGraphArtifacts(paths, { contract }) }).contractPath), true);

    const sourceMap = buildSourceFileToVaultPathMap(contract.manifest);
    assert.equal(sourceMap.get("raw/Wyckoff-Book.md"), "08-ai-kb/10-raw/books/Wyckoff-Book.md");

    const index = buildGraphNetworkIndexNote(config, "Wyckoff", paths);
    assert.match(index.content, /\[\[08-ai-kb\/10-raw\/books\/Wyckoff-Book.md\|Wyckoff Book\]\]/);
    assert.match(index.content, /Layer 1: Bridge Links/);

    const trace = buildGraphActivationTraceNote(config, "Wyckoff", paths);
    assert.match(trace.content, /Seed Activation/);
    assert.match(trace.content, /Two-hop spread/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("graphify refresh delegates the default request", () => {
  const calls = [];
  const result = runGraphifyTopicRefresh({ projectRoot: "C:\\repo\\obsidian-kb-local" }, "Topic Alpha", {
    runner(config, request) {
      calls.push({ config, request });
      return { ok: true };
    }
  });

  assert.equal(result.ok, true);
  assert.deepEqual(calls[0].request, buildGraphifyRefreshRequest("Topic Alpha"));
});

function createConfig(tempRoot) {
  return {
    vaultPath: path.join(tempRoot, "vault"),
    vaultName: "Test Vault",
    machineRoot: "08-ai-kb",
    projectRoot: tempRoot,
    obsidian: { cliCandidates: [], exeCandidates: [] }
  };
}

function writeRawNote(config, relativeFile, fields) {
  const notePath = path.join(config.vaultPath, config.machineRoot, "10-raw", relativeFile);
  fs.mkdirSync(path.dirname(notePath), { recursive: true });
  fs.writeFileSync(
    notePath,
    `${generateFrontmatter("raw", {
      source_type: fields.sourceType || "web_article",
      topic: fields.topic,
      source_url: "https://example.com/source",
      captured_at: "2026-04-04T10:00:00+08:00",
      kb_date: "2026-04-04",
      status: fields.status || "queued"
    })}

# ${path.basename(relativeFile, ".md")}

${fields.body}
`,
    "utf8"
  );
}

function writeWikiNote(config, relativeFile, fields) {
  const notePath = path.join(config.vaultPath, config.machineRoot, "20-wiki", relativeFile);
  fs.mkdirSync(path.dirname(notePath), { recursive: true });
  fs.writeFileSync(
    notePath,
    `${generateFrontmatter("wiki", {
      wiki_kind: fields.kind,
      topic: fields.topic,
      compiled_from: [`${config.machineRoot}/10-raw/web/Karpathy.md`],
      compiled_at: "2026-04-04T12:00:00+08:00",
      kb_date: "2026-04-04",
      review_state: "draft",
      kb_source_count: 1,
      dedup_key: `${fields.topic.toLowerCase()}::${fields.kind}`
    })}

# ${fields.title}

${fields.body}
`,
    "utf8"
  );
}
