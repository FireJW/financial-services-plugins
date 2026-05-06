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
import {
  buildEpubCompileDigest,
  buildEpubCompilePromptVariants,
  convertXhtmlToMarkdown,
  isFinanceRelatedBookCandidate,
  parseContainerRootfile,
  parseOpfPackage,
  selectFinanceRelatedBookNotes
} from "../src/epub-markdown.mjs";
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
  describeCodexProviderRoute,
  formatCodexProviderRouteDetail,
  loadCodexLlmProvider,
  parseTomlConfig
} from "../src/codex-config.mjs";
import {
  buildCodexThreadCaptureRequest,
  buildCodexThreadRawBody,
  captureCodexThreadToVault,
  normalizeCodexThreadUri
} from "../src/codex-thread-capture.mjs";
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
import { writeNote } from "../src/note-writer.mjs";
import {
  buildObsidianArgs,
  inferObsidianStdio,
  resolveObsidianEnvironment
} from "../src/obsidian-cli.mjs";
import {
  buildReferenceHubCompiledFrom,
  extractLinkedWikiPathsFromSection
} from "../src/reference-artifacts.mjs";
import {
  collectRollbackCandidates,
  executeRollback,
  writeRollbackLog
} from "../src/rollback.mjs";
import {
  buildQuerySynthesisNote,
  buildWikiQueryPrompt,
  selectRelevantWikiNotes
} from "../src/wiki-query.mjs";
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
import {
  buildGraphifySidecarReadme,
  buildGraphifyTopicPaths,
  buildGraphifyVaultNote,
  extractArtifactPathsFromMarkdown,
  resetGraphifyTopicWorkspace,
  scoreTopicSearchNote,
  selectTopicFallbackNotes,
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
  getCodexThreadAuditLogPath,
  getCodexThreadCaptureStatusPath,
  getCodexThreadRecoveryQueuePath,
  getDashboardPath,
  getGraphTopicStatusPath,
  getOpenQuestionsPath,
  getReferenceMapAuditPath,
  getSourcesByTopicPath,
  getStaleNotesPath,
  getTradingPsychologyMentorTemplatePath
} from "../src/view-paths.mjs";
import {
  buildTradingPsychologyTemplateNote,
  buildTradingPsychologyMentorFallbackResponse,
  buildTradingPsychologyMentorPrompt,
  resolveTradingPsychologyMentorTemplate,
  buildTradingPsychologyMentorSessionNote
} from "../src/trading-psychology-mentor.mjs";
import { decodeUnknownText } from "../src/stdin-text.mjs";
import {
  buildGraphifyRefreshRequest,
  runGraphifyTopicRefresh
} from "../src/graphify-refresh.mjs";
import { buildPoliticalEconomyRefreshPlan } from "../src/political-economy-suite.mjs";
import { buildTradingRefreshPlan } from "../src/trading-suite.mjs";
import { buildGraphTopicStatusContent, refreshWikiViews } from "../src/wiki-views.mjs";
import {
  describeProviderRoute,
  parseDoctorArgs
} from "../scripts/doctor.mjs";
import {
  parseCompileSourceArgs,
  runCompileSourceProviderProbe
} from "../scripts/compile-source.mjs";
import { parseCaptureCodexThreadArgs } from "../scripts/capture-codex-thread.mjs";
import {
  loadCodexThreadBatchManifest,
  parseCaptureCodexThreadBatchArgs,
  runCaptureCodexThreadBatch
} from "../scripts/capture-codex-thread-batch.mjs";
import {
  buildCodexThreadAuditReport,
  parseCodexThreadAuditReportArgs,
  runCodexThreadAuditReport
} from "../scripts/codex-thread-audit-report.mjs";
import {
  parseCodexThreadAuditDoctorArgs,
  runCodexThreadAuditDoctor
} from "../scripts/codex-thread-audit-doctor.mjs";
import {
  buildBackfillCodexThreadAuditRunIdsPlan,
  parseBackfillCodexThreadAuditRunIdsArgs,
  runBackfillCodexThreadAuditRunIds
} from "../scripts/backfill-codex-thread-audit-run-ids.mjs";
import {
  buildPruneCodexThreadAuditLogsPlan,
  parsePruneCodexThreadAuditLogsArgs,
  runPruneCodexThreadAuditLogs
} from "../scripts/prune-codex-thread-audit-logs.mjs";
import {
  buildCodexThreadBatchInitPlan,
  loadCodexThreadNameIndex,
  parseInitCodexThreadBatchArgs,
  parseThreadsFromText,
  runInitCodexThreadBatch
} from "../scripts/init-codex-thread-batch.mjs";
import {
  collectVerifyThreadUris,
  parseVerifyCodexThreadCaptureArgs,
  runVerifyCodexThreadCapture,
  verifyCodexThreadCapture
} from "../scripts/verify-codex-thread-capture.mjs";
import {
  buildReconcileCodexThreadCapturePlan,
  parseReconcileCodexThreadCaptureArgs,
  runReconcileCodexThreadCapture
} from "../scripts/reconcile-codex-thread-capture.mjs";
import {
  decideTopicRebuild,
  parseImportXIndexCliArgs
} from "../scripts/import-x-index-result.mjs";
import {
  appendRebuildTopicLog,
  buildTopicRebuildPromptVariants
} from "../scripts/rebuild-topic.mjs";
import {
  parseQueryWikiBatchCliArgs,
  parseQueriesFromText,
  runQueryWikiBatch
} from "../scripts/query-wiki-batch.mjs";
import {
  executeQueryWikiCommand,
  parseQueryWikiCliArgs,
  reportCliError
} from "../scripts/query-wiki.mjs";
import { parseTradingPsychologyMentorArgs } from "../scripts/trading-psychology-mentor.mjs";

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

run("doctor parser recognizes provider probe flags", () => {
  const parsed = parseDoctorArgs(["--probe-provider", "--timeout-ms", "120000"]);
  assert.equal(parsed.probeProvider, true);
  assert.equal(parsed.timeoutMs, 120000);
});

run("compile-source parser recognizes provider-only probe mode", () => {
  const parsed = parseCompileSourceArgs(["--probe-provider-only", "--timeout-ms", "250000"]);
  assert.equal(parsed.probeProviderOnly, true);
  assert.equal(parsed.compileTimeoutMs, 250000);
  assert.equal(parsed.topic, null);
  assert.equal(parsed.file, null);
});

run("codex thread uri normalizer accepts explicit uri and thread id", () => {
  assert.equal(
    normalizeCodexThreadUri("codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab"),
    "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab"
  );
  assert.equal(
    normalizeCodexThreadUri("", "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab"),
    "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab"
  );
  assert.equal(
    normalizeCodexThreadUri("", ""),
    "codex://threads/current-thread"
  );
});

run("codex thread capture builder wraps imported analysis with thread metadata", () => {
  const body = buildCodexThreadRawBody({
    threadUri: "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    body: "## Trade Card\n\nBase case.",
    capturedAt: "2026-04-08T12:45:00+08:00"
  });

  assert.match(body, /thread_uri: codex:\/\/threads\/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab/);
  assert.match(body, /## Imported Analysis/);
  assert.match(body, /## Trade Card/);
});

run("codex thread capture request maps into a manual raw note", () => {
  const request = buildCodexThreadCaptureRequest({
    threadId: "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    topic: "鐢电綉璁惧缁勫悎浜ゆ槗鍗＄墖",
    title: "2026-04-08 鍥界數鍗楃憺 + 涓浗瑗跨數 缁勫悎鍗＄墖",
    body: "缁勫悎鍒ゆ柇姝ｆ枃"
  });

  assert.equal(request.sourceType, "manual");
  assert.equal(request.topic, "鐢电綉璁惧缁勫悎浜ゆ槗鍗＄墖");
  assert.equal(request.sourceUrl, "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab");
  assert.match(request.body, /缁勫悎鍒ゆ柇姝ｆ枃/);
});

run("capture-codex-thread parser recognizes compile mode and thread id", () => {
  const parsed = parseCaptureCodexThreadArgs([
    "--thread-id",
    "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    "--topic",
    "鐢电綉璁惧缁勫悎浜ゆ槗鍗＄墖",
    "--title",
    "缁勫悎鍗＄墖",
    "--compile",
    "--timeout-ms",
    "240000"
  ]);

  assert.equal(parsed.threadId, "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab");
  assert.equal(parsed.compile, true);
  assert.equal(parsed.timeoutMs, 240000);
});

run("capture codex thread writes an explicit audit log entry", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-capture-log-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };

    const result = await captureCodexThreadToVault(
      config,
      {
        threadId: "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
        topic: "Audit Topic",
        title: "Audit Title",
        body: "## User Request\n\nTest\n\n## Assistant Response\n\nLogged."
      },
      {
        compile: false,
        skipLinks: true,
        skipViews: true,
        preferCli: false,
        allowFilesystemFallback: true
      }
    );

    assert.match(result.auditLogPath, /capture-codex-thread-\d{4}-\d{2}-\d{2}\.jsonl$/);
    const logContent = fs.readFileSync(result.auditLogPath, "utf8").trim().split(/\r?\n/);
    const lastEntry = JSON.parse(logContent.at(-1));
    assert.equal(lastEntry.action, "capture-codex-thread");
    assert.equal(lastEntry.thread_uri, "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab");
    assert.equal(lastEntry.topic, "Audit Topic");
    assert.equal(lastEntry.raw_note_path, "08-ai-kb/10-raw/manual/Audit-Title.md");
    assert.equal(lastEntry.raw_status, "queued");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("capture-codex-thread-batch parser recognizes manifest and fail-fast mode", () => {
  const parsed = parseCaptureCodexThreadBatchArgs([
    "--manifest",
    "examples/codex-thread-batch.template.json",
    "--compile",
    "--fail-fast",
    "--timeout-ms",
    "240000"
  ]);

  assert.match(parsed.manifestPath, /codex-thread-batch\.template\.json$/);
  assert.equal(parsed.compile, true);
  assert.equal(parsed.continueOnError, false);
  assert.equal(parsed.timeoutMs, 240000);
});

run("codex-thread-audit-report parser recognizes json mode", () => {
  const parsed = parseCodexThreadAuditReportArgs(["--json"]);
  assert.equal(parsed.json, true);
});

run("codex-thread-audit-doctor parser recognizes json mode and stale window", () => {
  const parsed = parseCodexThreadAuditDoctorArgs(["--json", "--stale-synthetic-days", "3"]);
  assert.equal(parsed.json, true);
  assert.equal(parsed.staleSyntheticDays, 3);
});

run("backfill-codex-thread-audit-run-ids parser recognizes apply mode", () => {
  const parsed = parseBackfillCodexThreadAuditRunIdsArgs(["--apply", "--json"]);
  assert.equal(parsed.apply, true);
  assert.equal(parsed.json, true);
});

run("prune-codex-thread-audit-logs parser recognizes apply and day window", () => {
  const parsed = parsePruneCodexThreadAuditLogsArgs(["--apply", "--days", "0", "--json"]);
  assert.equal(parsed.apply, true);
  assert.equal(parsed.days, 0);
  assert.equal(parsed.json, true);
});

run("init-codex-thread-batch parser accepts output dir and thread sources", () => {
  const parsed = parseInitCodexThreadBatchArgs([
    "--output-dir",
    ".tmp/codex-batch",
    "--thread-id",
    "019d5746-28de-7631-ad1c-d35ca5815b94",
    "--thread-uri",
    "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    "--topic",
    "鎵归噺娌夋穩",
    "--title-prefix",
    "鍘嗗彶绾跨▼",
    "--no-compile"
  ]);

  assert.match(parsed.outputDir, /codex-batch$/);
  assert.equal(parsed.threadIds.length, 1);
  assert.equal(parsed.threadUris.length, 1);
  assert.equal(parsed.topic, "鎵归噺娌夋穩");
  assert.equal(parsed.titlePrefix, "鍘嗗彶绾跨▼");
  assert.equal(parsed.compile, false);
});

run("init-codex-thread-batch parses thread lists from text", () => {
  assert.deepEqual(
    parseThreadsFromText(`
# comments
codex://threads/aaa

bbb
`),
    ["codex://threads/aaa", "bbb"]
  );
});

run("init-codex-thread-batch plan creates manifest entries and body templates", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-init-codex-thread-batch-plan-"));

  try {
    const threadsFile = path.join(tempRoot, "threads.txt");
    fs.writeFileSync(
      threadsFile,
      "019d5746-28de-7631-ad1c-d35ca5815b94\ncodex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab\n",
      "utf8"
    );

    const plan = buildCodexThreadBatchInitPlan({
      outputDir: path.join(tempRoot, "out"),
      threadsFile,
      threadUris: [],
      threadIds: [],
      topic: "鎵归噺娌夋穩",
      titlePrefix: "鍘嗗彶绾跨▼",
      sourceLabel: "Codex batch import",
      compile: true
    });

    assert.equal(plan.entries.length, 2);
    assert.equal(plan.manifest.defaults.compile, true);
    assert.equal(plan.manifest.entries[0].topic, "鎵归噺娌夋穩");
    assert.match(plan.entries[0].bodyPath, /bodies/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("init-codex-thread-batch uses session_index thread names", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-init-codex-thread-batch-name-"));

  try {
    const sessionIndexPath = path.join(tempRoot, "session_index.jsonl");
    fs.writeFileSync(
      sessionIndexPath,
      [
        JSON.stringify({
          id: "019dfe10-7cc1-71b1-b507-a7674a74aa68",
          thread_name: "multi platform handoff",
          updated_at: "2026-05-06T16:13:24.7392599Z"
        }),
        ""
      ].join("\n"),
      "utf8"
    );

    const plan = buildCodexThreadBatchInitPlan({
      outputDir: path.join(tempRoot, "out"),
      sessionIndexPath,
      threadIds: ["019dfe10-7cc1-71b1-b507-a7674a74aa68"],
      threadUris: [],
      topic: "Codex thread archive",
      titlePrefix: "Thread",
      sourceLabel: "Codex batch import",
      compile: true
    });

    assert.equal(
      loadCodexThreadNameIndex(sessionIndexPath).get("019dfe10-7cc1-71b1-b507-a7674a74aa68")
        .threadName,
      "multi platform handoff"
    );
    assert.equal(plan.entries[0].threadName, "multi platform handoff");
    assert.equal(plan.manifest.entries[0].thread_name, "multi platform handoff");
    assert.equal(plan.manifest.entries[0].title, "Thread - multi platform handoff");
    assert.match(plan.entries[0].bodyTemplate, /Thread name: multi platform handoff/);
    assert.match(plan.entries[0].bodyTemplate, /# Codex Thread Capture\n\nThread URI:/);
    assert.match(plan.entries[0].bodyTemplate, /Topic: Codex thread archive\n\n## User Request/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("init-codex-thread-batch writes manifest and body template files", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-init-codex-thread-batch-run-"));
  const writes = [];

  try {
    await runInitCodexThreadBatch(
      [
        "--output-dir",
        path.join(tempRoot, "out"),
        "--thread-id",
        "019d5746-28de-7631-ad1c-d35ca5815b94",
        "--topic",
        "鎵归噺娌夋穩",
        "--title-prefix",
        "鍘嗗彶绾跨▼"
      ],
      {
        writer: {
          log(line = "") {
            writes.push(String(line));
          }
        }
      }
    );

    const manifestPath = path.join(tempRoot, "out", "manifest.json");
    const bodiesDir = path.join(tempRoot, "out", "bodies");
    const files = fs.readdirSync(bodiesDir);

    assert.equal(fs.existsSync(manifestPath), true);
    assert.equal(files.length, 1);
    assert.match(fs.readFileSync(path.join(bodiesDir, files[0]), "utf8"), /## User Request/);
    assert.match(writes.join("\n"), /Batch manifest:/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("verify-codex-thread-capture parser accepts multiple input sources", () => {
  const parsed = parseVerifyCodexThreadCaptureArgs([
    "--manifest",
    "examples/codex-thread-batch.template.json",
    "--thread-id",
    "019d5746-28de-7631-ad1c-d35ca5815b94",
    "--thread-uri",
    "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    "--json"
  ]);

  assert.match(parsed.manifestPath, /codex-thread-batch\.template\.json$/);
  assert.equal(parsed.threadIds.length, 1);
  assert.equal(parsed.threadUris.length, 1);
  assert.equal(parsed.json, true);
});

run("verify-codex-thread-capture collects uris from manifest threads file and args", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-verify-codex-thread-collect-"));

  try {
    const threadsFile = path.join(tempRoot, "threads.txt");
    const manifestPath = path.join(tempRoot, "manifest.json");
    fs.writeFileSync(threadsFile, "019d5746-28de-7631-ad1c-d35ca5815b94\n", "utf8");
    fs.writeFileSync(
      manifestPath,
      JSON.stringify({
        entries: [
          {
            thread_uri: "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
            topic: "x",
            title: "y",
            body: "z"
          }
        ]
      }),
      "utf8"
    );

    const uris = collectVerifyThreadUris({
      manifestPath,
      threadsFile,
      threadUris: ["codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab"],
      threadIds: ["019d5746-28de-7631-ad1c-d35ca5815b94"]
    });

    assert.deepEqual(uris.sort(), [
      "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
      "codex://threads/019d5746-28de-7631-ad1c-d35ca5815b94"
    ]);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

/*
run("verify-codex-thread-capture finds raw and wiki matches", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-verify-codex-thread-vault-"));

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = path.join(vaultPath, machineRoot, "10-raw", "manual", "Thread-A.md");
    const wikiPath = path.join(vaultPath, machineRoot, "20-wiki", "sources", "Thread-A-source.md");
    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.mkdirSync(path.dirname(wikiPath), { recursive: true });

    fs.writeFileSync(
      rawPath,
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "娴嬭瘯涓婚"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n\n## Thread Source\n\n- thread_uri: codex://threads/thread-a\n`,
      "utf8"
    );

    fs.writeFileSync(
      wikiPath,
      `---\nkb_type: "wiki"\nwiki_kind: "source"\ntopic: "娴嬭瘯涓婚"\ncompiled_from: ["08-AI鐭ヨ瘑搴?10-raw/manual/Thread-A.md"]\ncompiled_at: "2026-04-08T00:05:00+08:00"\nkb_date: "2026-04-08"\nreview_state: "draft"\nmanaged_by: "codex"\nkb_source_count: 1\ndedup_key: "娴嬭瘯涓婚::source::codex://threads/thread-a"\n---\n\n# Thread A Source\n`,
      "utf8"
    );

    const results = verifyCodexThreadCapture(
      {
        vaultPath,
        machineRoot
      },
      ["codex://threads/thread-a", "codex://threads/thread-b"]
    );

    assert.equal(results[0].ok, true);
    assert.equal(results[0].rawCount, 1);
    assert.equal(results[0].wikiCount, 1);
    assert.equal(results[1].ok, false);
    assert.equal(results[1].rawCount, 0);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("verify-codex-thread-capture reports json output for matched threads", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-verify-codex-thread-json-"));
  const writes = [];

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = path.join(vaultPath, machineRoot, "10-raw", "manual", "Thread-A.md");
    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.writeFileSync(
      rawPath,
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "娴嬭瘯涓婚"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n`,
      "utf8"
    );

    const results = await runVerifyCodexThreadCapture(
      ["--thread-id", "thread-a", "--json"],
      {
        config: {
          vaultPath,
          machineRoot,
          projectRoot: tempRoot
        },
        writer: {
          log(line = "") {
            writes.push(String(line));
          }
        }
      }
    );

    assert.equal(results.length, 1);
    assert.equal(results[0].ok, true);
    assert.match(writes.join("\n"), /"threadUri": "codex:\/\/threads\/thread-a"/);
    const verifyLogFiles = fs
      .readdirSync(path.join(tempRoot, "logs"))
      .filter((entry) => entry.startsWith("verify-codex-thread-capture-"));
    assert.equal(verifyLogFiles.length, 1);
    const verifyLogContent = fs.readFileSync(
      path.join(tempRoot, "logs", verifyLogFiles[0]),
      "utf8"
    );
    assert.match(verifyLogContent, /"captured":1/);
    assert.match(verifyLogContent, /codex:\/\/threads\/thread-a/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("reconcile-codex-thread-capture parser requires output dir and thread source", () => {
  const parsed = parseReconcileCodexThreadCaptureArgs([
    "--output-dir",
    ".tmp/reconcile",
    "--thread-id",
    "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    "--topic",
    "琛ュ綍涓婚",
    "--title-prefix",
    "Missing Thread",
    "--no-compile"
  ]);

  assert.match(parsed.outputDir, /reconcile$/);
  assert.equal(parsed.threadIds.length, 1);
  assert.equal(parsed.topic, "琛ュ綍涓婚");
  assert.equal(parsed.compile, false);
});

run("reconcile-codex-thread-capture plan keeps only missing threads", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-reconcile-codex-thread-plan-"));

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = path.join(vaultPath, machineRoot, "10-raw", "manual", "Thread-A.md");
    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.writeFileSync(
      rawPath,
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "娴嬭瘯涓婚"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n`,
      "utf8"
    );

    const plan = buildReconcileCodexThreadCapturePlan(
      {
        vaultPath,
        machineRoot
      },
      {
        outputDir: path.join(tempRoot, "out"),
        manifestPath: "",
        threadsFile: "",
        threadUris: ["codex://threads/thread-a", "codex://threads/thread-b"],
        threadIds: [],
        topic: "琛ュ綍涓婚",
        titlePrefix: "Missing Thread",
        sourceLabel: "Codex reconciliation",
        compile: true,
        json: false
      }
    );

    assert.equal(plan.report.total, 2);
    assert.equal(plan.report.captured, 1);
    assert.equal(plan.report.missing, 1);
    assert.equal(plan.batchManifest.entries.length, 1);
    assert.equal(plan.batchManifest.entries[0].thread_uri, "codex://threads/thread-b");
    assert.equal(plan.bodyFiles.length, 1);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("reconcile-codex-thread-capture writes report and missing manifest", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-reconcile-codex-thread-run-"));
  const writes = [];

  try {
    await runReconcileCodexThreadCapture(
      [
        "--output-dir",
        path.join(tempRoot, "out"),
        "--thread-id",
        "thread-missing"
      ],
      {
        config: {
          vaultPath: path.join(tempRoot, "vault"),
          projectRoot: tempRoot,
          machineRoot: "08-ai-kb",
        },
        writer: {
          log(line = "") {
            writes.push(String(line));
          }
        }
      }
    );

    assert.equal(fs.existsSync(path.join(tempRoot, "out", "verification-report.json")), true);
    assert.equal(fs.existsSync(path.join(tempRoot, "out", "missing-manifest.json")), true);
    assert.match(writes.join("\n"), /Summary: total=1, captured=0, missing=1/);
    const reconcileLogFiles = fs
      .readdirSync(path.join(tempRoot, "logs"))
      .filter((entry) => entry.startsWith("reconcile-codex-thread-capture-"));
    assert.equal(reconcileLogFiles.length, 1);
    const reconcileLogContent = fs.readFileSync(
      path.join(tempRoot, "logs", reconcileLogFiles[0]),
      "utf8"
    );
    assert.match(reconcileLogContent, /"missing":1/);
    assert.match(reconcileLogContent, /thread-missing/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});
*/

run("verify-codex-thread-capture finds raw and wiki matches", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-verify-codex-thread-vault-"));

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = path.join(vaultPath, machineRoot, "10-raw", "manual", "Thread-A.md");
    const wikiPath = path.join(vaultPath, machineRoot, "20-wiki", "sources", "Thread-A-source.md");
    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.mkdirSync(path.dirname(wikiPath), { recursive: true });

    fs.writeFileSync(
      rawPath,
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "Test Topic"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n\n## Thread Source\n\n- thread_uri: codex://threads/thread-a\n`,
      "utf8"
    );

    fs.writeFileSync(
      wikiPath,
      `---\nkb_type: "wiki"\nwiki_kind: "source"\ntopic: "Test Topic"\ncompiled_from: ["08-ai-kb/10-raw/manual/Thread-A.md"]\ncompiled_at: "2026-04-08T00:05:00+08:00"\nkb_date: "2026-04-08"\nreview_state: "draft"\nmanaged_by: "codex"\nkb_source_count: 1\ndedup_key: "test topic::source::codex://threads/thread-a"\n---\n\n# Thread A Source\n`,
      "utf8"
    );

    const results = verifyCodexThreadCapture(
      {
        vaultPath,
        machineRoot
      },
      ["codex://threads/thread-a", "codex://threads/thread-b"]
    );

    assert.equal(results[0].ok, true);
    assert.equal(results[0].rawCount, 1);
    assert.equal(results[0].wikiCount, 1);
    assert.equal(results[1].ok, false);
    assert.equal(results[1].rawCount, 0);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("verify-codex-thread-capture reports json output for matched threads", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-verify-codex-thread-json-"));
  const writes = [];

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = path.join(vaultPath, machineRoot, "10-raw", "manual", "Thread-A.md");
    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.writeFileSync(
      rawPath,
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "Test Topic"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n`,
      "utf8"
    );

    const results = await runVerifyCodexThreadCapture(
      ["--thread-id", "thread-a", "--json"],
      {
        config: {
          vaultPath,
          machineRoot,
          projectRoot: tempRoot
        },
        writer: {
          log(line = "") {
            writes.push(String(line));
          }
        }
      }
    );

    assert.equal(results.length, 1);
    assert.equal(results[0].ok, true);
    assert.match(writes.join("\n"), /"threadUri": "codex:\/\/threads\/thread-a"/);
    const verifyLogFiles = fs
      .readdirSync(path.join(tempRoot, "logs"))
      .filter((entry) => entry.startsWith("verify-codex-thread-capture-"));
    assert.equal(verifyLogFiles.length, 1);
    const verifyLogContent = fs.readFileSync(
      path.join(tempRoot, "logs", verifyLogFiles[0]),
      "utf8"
    );
    assert.match(verifyLogContent, /"captured":1/);
    assert.match(verifyLogContent, /codex:\/\/threads\/thread-a/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("reconcile-codex-thread-capture parser requires output dir and thread source", () => {
  const parsed = parseReconcileCodexThreadCaptureArgs([
    "--output-dir",
    ".tmp/reconcile",
    "--thread-id",
    "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    "--topic",
    "Reconcile Topic",
    "--title-prefix",
    "Missing Thread",
    "--no-compile"
  ]);

  assert.match(parsed.outputDir, /reconcile$/);
  assert.equal(parsed.threadIds.length, 1);
  assert.equal(parsed.topic, "Reconcile Topic");
  assert.equal(parsed.compile, false);
});

run("reconcile-codex-thread-capture plan keeps only missing threads", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-reconcile-codex-thread-plan-"));

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = path.join(vaultPath, machineRoot, "10-raw", "manual", "Thread-A.md");
    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.writeFileSync(
      rawPath,
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "Test Topic"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n`,
      "utf8"
    );

    const plan = buildReconcileCodexThreadCapturePlan(
      {
        vaultPath,
        machineRoot
      },
      {
        outputDir: path.join(tempRoot, "out"),
        manifestPath: "",
        threadsFile: "",
        threadUris: ["codex://threads/thread-a", "codex://threads/thread-b"],
        threadIds: [],
        topic: "Reconcile Topic",
        titlePrefix: "Missing Thread",
        sourceLabel: "Codex reconciliation",
        compile: true,
        json: false
      }
    );

    assert.equal(plan.report.total, 2);
    assert.equal(plan.report.captured, 1);
    assert.equal(plan.report.missing, 1);
    assert.equal(plan.batchManifest.entries.length, 1);
    assert.equal(plan.batchManifest.entries[0].thread_uri, "codex://threads/thread-b");
    assert.equal(plan.bodyFiles.length, 1);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("reconcile-codex-thread-capture writes report and missing manifest", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-reconcile-codex-thread-run-"));
  const writes = [];

  try {
    await runReconcileCodexThreadCapture(
      [
        "--output-dir",
        path.join(tempRoot, "out"),
        "--thread-id",
        "thread-missing"
      ],
      {
        config: {
          vaultPath: path.join(tempRoot, "vault"),
          machineRoot: "08-ai-kb",
          projectRoot: tempRoot
        },
        writer: {
          log(line = "") {
            writes.push(String(line));
          }
        }
      }
    );

    assert.equal(fs.existsSync(path.join(tempRoot, "out", "verification-report.json")), true);
    assert.equal(fs.existsSync(path.join(tempRoot, "out", "missing-manifest.json")), true);
    assert.match(writes.join("\n"), /Summary: total=1, captured=0, missing=1/);
    const reconcileLogFiles = fs
      .readdirSync(path.join(tempRoot, "logs"))
      .filter((entry) => entry.startsWith("reconcile-codex-thread-capture-"));
    assert.equal(reconcileLogFiles.length, 1);
    const reconcileLogContent = fs.readFileSync(
      path.join(tempRoot, "logs", reconcileLogFiles[0]),
      "utf8"
    );
    assert.match(reconcileLogContent, /"missing":1/);
    assert.match(reconcileLogContent, /thread-missing/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("codex thread batch manifest loads defaults and resolves relative body files", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-batch-manifest-"));

  try {
    const bodyPath = path.join(tempRoot, "entry-1.md");
    const manifestPath = path.join(tempRoot, "batch.json");
    fs.writeFileSync(bodyPath, "## Captured\n\nBody from file.\n", "utf8");
    fs.writeFileSync(
      manifestPath,
      JSON.stringify(
        {
          defaults: {
            source_label: "Codex batch import",
            compile: true
          },
          entries: [
            {
              thread_id: "019d5746-28de-7631-ad1c-d35ca5815b94",
              topic: "batch-topic",
              title: "entry-one",
              body_file: "entry-1.md"
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    const manifest = loadCodexThreadBatchManifest(manifestPath);
    assert.equal(manifest.entries.length, 1);
    assert.equal(manifest.entries[0].sourceLabel, "Codex batch import");
    assert.equal(manifest.entries[0].compile, true);
    assert.match(manifest.entries[0].body, /Body from file/);
    assert.equal(manifest.entries[0].threadId, "019d5746-28de-7631-ad1c-d35ca5815b94");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("codex thread batch manifest tolerates utf8 bom", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-batch-bom-"));

  try {
    const manifestPath = path.join(tempRoot, "batch.json");
    fs.writeFileSync(
      manifestPath,
      `\uFEFF${JSON.stringify({
        entries: [
          {
            topic: "鎵归噺绾跨▼瀵煎叆",
            title: "BOM entry",
            body: "BOM body"
          }
        ]
      })}`,
      "utf8"
    );

    const manifest = loadCodexThreadBatchManifest(manifestPath);
    assert.equal(manifest.entries.length, 1);
    assert.equal(manifest.entries[0].title, "BOM entry");
    assert.equal(manifest.entries[0].body, "BOM body");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("codex thread batch runs captures and refreshes links/views once", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-batch-run-"));
  const writes = [];
  const errors = [];
  const captures = [];
  const summary = await runCaptureCodexThreadBatch(
    {
      manifestPath: "ignored.json",
      compile: true,
      skipLinks: false,
      skipViews: false,
      continueOnError: true,
      timeoutMs: 240000
    },
    {
      config: {
        projectRoot: tempRoot
      },
      manifest: {
        path: path.join(tempRoot, "batch.json"),
        entries: [
          {
            threadUri: "codex://threads/a",
            topic: "topic-a",
            title: "Entry A",
            body: "A",
            compile: true
          },
          {
            threadUri: "codex://threads/b",
            topic: "topic-b",
            title: "Entry B",
            body: "B",
            compile: false
          }
        ]
      },
      writer: {
        log(line = "") {
          writes.push(String(line));
        },
        error(line = "") {
          errors.push(String(line));
        }
      },
      loadProviderFn() {
        return {
          providerName: "openai",
          model: "gpt-5.4",
          baseUrl: "https://api.openai.com/v1",
          wireApi: "responses",
          configPath: "C:\\Users\\exampleuser\\.codex\\config.toml"
        };
      },
      templateContent: "RAW={{RAW_CONTENT}}\nTOPIC={{TOPIC}}",
      captureFn: async (_config, entry, options) => {
        captures.push({
          title: entry.title,
          compile: options.compile,
          skipLinks: options.skipLinks,
          skipViews: options.skipViews
        });
        return {
          ingestResult: {
            path: `08-AI鐭ヨ瘑搴?10-raw/manual/${entry.title}.md`,
            mode: "filesystem-fallback"
          },
          compileResult: options.compile
            ? {
                ok: true,
                response: {
                  endpoint: "https://api.openai.com/v1/responses"
                },
                applyResult: {
                  logFile: "compile-log.jsonl",
                  results: []
                }
              }
            : null
        };
      },
      rebuildLinksFn() {
        return {
          updated: 2,
          scanned: 10
        };
      },
      refreshViewsFn() {
        return [
          {
            path: "08-AI鐭ヨ瘑搴?20-wiki/_index.md",
            mode: "filesystem-fallback"
          }
        ];
      }
    }
  );

  assert.equal(summary.total, 2);
  assert.equal(summary.completed, 2);
  assert.equal(summary.failed, 0);
  assert.match(summary.auditLogPath, /capture-codex-thread-batch-\d{4}-\d{2}-\d{2}\.jsonl$/);
  assert.equal(fs.existsSync(summary.auditLogPath), true);
  assert.deepEqual(
    captures.map((entry) => [entry.title, entry.compile, entry.skipLinks, entry.skipViews]),
    [
      ["Entry A", true, true, true],
      ["Entry B", false, true, true]
    ]
  );
  assert.match(writes.join("\n"), /Rebuilt automatic links for 2 note\(s\) out of 10 scanned/);
  assert.match(writes.join("\n"), /Batch summary: total=2, completed=2, failed=0/);
  assert.match(writes.join("\n"), /Batch audit log:/);
  assert.deepEqual(errors, []);
  fs.rmSync(tempRoot, { recursive: true, force: true });
});

run("codex thread audit report summarizes capture batch verify and reconcile logs", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-audit-report-"));
  const writes = [];

  try {
    const logDirectory = path.join(tempRoot, "logs");
    fs.mkdirSync(logDirectory, { recursive: true });
    fs.writeFileSync(
      path.join(logDirectory, "capture-codex-thread-2026-04-08.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-08T10:00:00+08:00",
        action: "capture-codex-thread",
        thread_uri: "codex://threads/current-thread",
        raw_status: "compiled"
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "capture-codex-thread-batch-2026-04-08.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-08T10:05:00+08:00",
        action: "capture-codex-thread-batch",
        manifest_path: "C:/repo/obsidian-kb-local/.tmp/batch.json",
        total: 2,
        completed: 2,
        failed: 0
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "verify-codex-thread-capture-2026-04-08.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-08T10:10:00+08:00",
        captured: 1,
        missing: 0
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "reconcile-codex-thread-capture-2026-04-08.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-08T10:15:00+08:00",
        captured: 1,
        missing: 1,
        manifest_path: "C:/repo/obsidian-kb-local/.tmp/missing-manifest.json"
      })}\n`,
      "utf8"
    );

    const report = buildCodexThreadAuditReport({
      projectRoot: tempRoot
    });
    assert.equal(report.summary.capture_events, 1);
    assert.equal(report.summary.capture_batch_events, 1);
    assert.equal(report.summary.verify_events, 1);
    assert.equal(report.summary.reconcile_events, 1);
    assert.equal(report.summary.pending_recovery_runs, 1);
    assert.equal(report.pending_recovery.manifest_path, "C:/repo/obsidian-kb-local/.tmp/missing-manifest.json");

    await runCodexThreadAuditReport(["--json"], {
      config: {
        projectRoot: tempRoot
      },
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      }
    });

    assert.match(writes.join("\n"), /"capture_events": 1/);
    assert.match(writes.join("\n"), /"capture_batch_events": 1/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("prune codex thread audit logs archives expired synthetic entries", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-prune-codex-thread-audit-logs-"));
  const writes = [];

  try {
    const logDirectory = path.join(tempRoot, "logs");
    fs.mkdirSync(logDirectory, { recursive: true });
    const sourcePath = path.join(logDirectory, "reconcile-codex-thread-capture-2026-04-01.jsonl");
    fs.writeFileSync(
      sourcePath,
      `${JSON.stringify({
        timestamp: "2026-04-01T10:00:00+08:00",
        synthetic: true,
        note: "validation-demo",
        missing: 1
      })}\n${JSON.stringify({
        timestamp: "2026-04-08T10:00:00+08:00",
        missing: 0
      })}\n`,
      "utf8"
    );

    const plan = buildPruneCodexThreadAuditLogsPlan(
      { projectRoot: tempRoot },
      { apply: false, days: 0, json: false },
      new Date("2026-04-08T12:00:00+08:00")
    );
    assert.equal(plan.archivedEntries, 1);
    assert.equal(plan.filePlans.length, 1);

    await runPruneCodexThreadAuditLogs(["--apply", "--days", "0", "--json"], {
      config: { projectRoot: tempRoot },
      now: new Date("2026-04-08T12:00:00+08:00"),
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      }
    });

    const remaining = fs.readFileSync(sourcePath, "utf8");
    assert.doesNotMatch(remaining, /validation-demo/);
    assert.match(remaining, /"missing":0/);

    const archivePath = path.join(logDirectory, "archive", "reconcile-codex-thread-capture-2026-04-01.jsonl");
    assert.equal(fs.existsSync(archivePath), true);
    const archived = fs.readFileSync(archivePath, "utf8");
    assert.match(archived, /validation-demo/);
    assert.match(writes.join("\n"), /"archivedEntries": 1/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("codex thread audit doctor flags missing run ids and stale synthetic entries", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-audit-doctor-"));
  const writes = [];

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = path.join(vaultPath, machineRoot, "10-raw", "manual", "Captured.md");
    const wikiPath = path.join(vaultPath, machineRoot, "20-wiki", "sources", "Captured-Source.md");
    const logDirectory = path.join(tempRoot, "logs");
    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.mkdirSync(path.dirname(wikiPath), { recursive: true });
    fs.mkdirSync(logDirectory, { recursive: true });

    fs.writeFileSync(
      rawPath,
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "Audit Topic",
        source_url: "codex://threads/thread-a",
        captured_at: "2026-04-08T10:00:00+08:00",
        status: "compiled"
      })}\n\n# Captured\n`,
      "utf8"
    );
    fs.writeFileSync(
      wikiPath,
      `${generateFrontmatter("wiki", {
        wiki_kind: "source",
        topic: "Audit Topic",
        compiled_from: ["08-ai-kb/10-raw/manual/Captured.md"],
        compiled_at: "2026-04-08T10:05:00+08:00",
        kb_source_count: 1,
        dedup_key: "audit topic::source::codex://threads/thread-a"
      })}\n\n# Captured Source\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "capture-codex-thread-2026-04-08.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-08T10:00:00+08:00",
        action: "capture-codex-thread",
        thread_uri: "codex://threads/thread-a",
        raw_note_path: "08-ai-kb/10-raw/manual/Captured.md",
        raw_status: "compiled"
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "reconcile-codex-thread-capture-2026-04-01.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-01T10:00:00+08:00",
        synthetic: true,
        note: "validation-demo",
        missing: 1,
        manifest_path: "C:/tmp/missing-manifest.json",
        report_path: "C:/tmp/verification-report.json",
        output_dir: "C:/tmp/out"
      })}\n`,
      "utf8"
    );

    const report = await runCodexThreadAuditDoctor(["--json", "--stale-synthetic-days", "3"], {
      config: {
        projectRoot: tempRoot,
        vaultPath,
        machineRoot
      },
      now: new Date("2026-04-08T12:00:00+08:00"),
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      }
    });

    assert.equal(report.status, "warn");
    assert.ok(report.checks.some((check) => check.id === "missing-run-id" && check.count >= 1));
    assert.ok(report.checks.some((check) => check.id === "stale-synthetic-audit-entries" && check.count === 1));
    assert.match(writes.join("\n"), /"status": "warn"/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("backfill codex thread audit run ids updates legacy entries", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-backfill-codex-thread-run-ids-"));
  const writes = [];

  try {
    const logDirectory = path.join(tempRoot, "logs");
    fs.mkdirSync(logDirectory, { recursive: true });
    const logPath = path.join(logDirectory, "verify-codex-thread-capture-2026-04-08.jsonl");
    fs.writeFileSync(
      logPath,
      `${JSON.stringify({
        timestamp: "2026-04-08T10:00:00+08:00",
        action: "verify-codex-thread-capture",
        captured: 1,
        missing: 0
      })}\n`,
      "utf8"
    );

    const plan = buildBackfillCodexThreadAuditRunIdsPlan({ projectRoot: tempRoot });
    assert.equal(plan.updatedEntries, 1);
    assert.equal(plan.filePlans.length, 1);

    await runBackfillCodexThreadAuditRunIds(["--apply", "--json"], {
      config: { projectRoot: tempRoot },
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      }
    });

    const updated = JSON.parse(fs.readFileSync(logPath, "utf8").trim());
    assert.match(updated.run_id, /^legacy-/);
    assert.equal(updated.run_id_source, "backfill");
    assert.match(writes.join("\n"), /"updatedEntries": 1/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("compile-source provider probe reports endpoint and route", async () => {
  const writes = [];
  const result = await runCompileSourceProviderProbe(
    {
      projectRoot: "C:\\repo\\obsidian-kb-local"
    },
    {
      timeoutMs: 123000,
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      },
      loadProvider() {
        return {
          providerName: "openai",
          model: "gpt-5.4",
          baseUrl: "https://api.openai.com/v1",
          wireApi: "responses",
          configPath: "C:\\Users\\exampleuser\\.codex\\config.toml",
          authMode: "chatgpt",
          apiKey: null,
          requiresOpenAiAuth: true,
          canUseChatGptSession: true
        };
      },
      callProvider: async () => ({
        endpoint: "codex exec",
        outputText: "OK"
      })
    }
  );

  assert.equal(result.response.endpoint, "codex exec");
  assert.match(writes.join("\n"), /Provider route: .*route:codex-exec-fallback/);
  assert.match(writes.join("\n"), /Provider probe: OK via codex exec -> OK/);
});

run("rebuild-topic log appends provider route and endpoint", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-rebuild-topic-log-run-tests-"));

  try {
    const logFile = appendRebuildTopicLog(tempRoot, "2026-04-08T12:00:00+08:00", {
      timestamp: "2026-04-08T12:00:00+08:00",
      topic: "AI knowledge workflows",
      status: "ok",
      provider: "openai",
      model: "gpt-5.4",
      provider_route:
        "openai | gpt-5.4 | responses | https://api.openai.com/v1 (route:codex-exec-fallback, auth-mode:chatgpt, api-key:missing)",
      provider_endpoint: "codex exec",
      total_results: 3
    });

    const entry = JSON.parse(fs.readFileSync(logFile, "utf8").trim());
    assert.equal(entry.topic, "AI knowledge workflows");
    assert.equal(entry.provider_endpoint, "codex exec");
    assert.match(entry.provider_route, /route:codex-exec-fallback/);
    assert.equal(entry.total_results, 3);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("rebuild-topic prompt variants fall back to compact snapshots for oversized topics", () => {
  const largeBody = "# Heading\n\n" + "A".repeat(12000);
  const variants = buildTopicRebuildPromptVariants(
    "# Rebuild",
    {
      topic: "trading",
      rawNotes: Array.from({ length: 6 }, (_, index) => ({
        title: `Raw ${index + 1}`,
        relativePath: `08-AI鐭ヨ瘑搴?10-raw/manual/raw-${index + 1}.md`,
        frontmatter: {
          source_type: "manual",
          source_url: `https://example.com/raw-${index + 1}`,
          captured_at: "2026-04-08T00:00:00+08:00"
        },
        content: `---\nkb_type: "raw"\n---\n\n${largeBody}`
      })),
      wikiNotes: Array.from({ length: 8 }, (_, index) => ({
        title: `Wiki ${index + 1}`,
        relativePath: `08-AI鐭ヨ瘑搴?20-wiki/concepts/wiki-${index + 1}.md`,
        frontmatter: {
          wiki_kind: "concept",
          compiled_from: [`08-AI鐭ヨ瘑搴?10-raw/manual/raw-${(index % 6) + 1}.md`]
        },
        content: `---\nkb_type: "wiki"\n---\n\n# Wiki ${index + 1}\n\n${largeBody}`
      }))
    }
  );

  assert.equal(variants[0].label, "compact-42000");
  assert.equal(variants.some((variant) => variant.label === "full"), false);
  assert.equal(variants.length >= 2, true);
  assert.equal(variants[0].prompt.length < 60000, true);
  assert.match(variants[0].prompt, /\[compact snapshot truncated\]/);
});

run("doctor provider route prefers codex exec fallback for chatgpt auth mode", () => {
  const route = describeProviderRoute({
    providerName: "openai",
    authMode: "chatgpt",
    apiKey: null,
    requiresOpenAiAuth: true,
    canUseChatGptSession: true
  });

  assert.equal(route.ok, true);
  assert.equal(route.route, "codex-exec-fallback");
  assert.ok(route.flags.includes("route:codex-exec-fallback"));
  assert.ok(route.flags.includes("auth-mode:chatgpt"));
});

run("doctor provider route blocks missing api key without chatgpt fallback", () => {
  const route = describeProviderRoute({
    providerName: "custom",
    authMode: "api_key",
    apiKey: null,
    requiresOpenAiAuth: true,
    canUseChatGptSession: false
  });

  assert.equal(route.ok, false);
  assert.equal(route.route, "blocked");
  assert.ok(route.flags.includes("api-key:missing"));
});

run("doctor provider route explains that chatgpt auth does not unlock custom gateways", () => {
  const route = describeProviderRoute({
    providerName: "custom",
    authMode: "chatgpt",
    apiKey: null,
    requiresOpenAiAuth: true,
    canUseChatGptSession: false
  });

  assert.equal(route.ok, false);
  assert.equal(route.route, "blocked");
  assert.ok(route.flags.includes("auth-mode:chatgpt"));
  assert.ok(route.flags.includes("chatgpt-session:openai-only"));
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

run("obsidian cli uses ignore stdio for write-like commands and pipe for reads", () => {
  assert.equal(inferObsidianStdio(["create", "path=test.md"]), "ignore");
  assert.equal(inferObsidianStdio(["append", "path=test.md"]), "ignore");
  assert.equal(inferObsidianStdio(["read", "path=test.md"]), "pipe");
  assert.equal(inferObsidianStdio(["search", "query=money supply"]), "pipe");
  assert.equal(inferObsidianStdio(["read", "path=test.md"], { stdio: "inherit" }), "inherit");
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
      hasRunningObsidianProcess() {
        return true;
      },
      pathExists(candidate) {
        return candidate === "C:\\Obsidian\\Obsidian.exe";
      }
    }
  );

  assert.equal(env.cliCommand, "obsidian");
  assert.equal(env.cliMode, "registered-command");
  assert.equal(env.exePath, "C:\\Obsidian\\Obsidian.exe");
  assert.equal(env.appRunning, true);
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
  const inferredPath = "C:\\Users\\exampleuser\\AppData\\Local\\Programs\\obsidian\\Obsidian.exe";
  const env = resolveObsidianEnvironment(
    {
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: []
      }
    },
    {
      env: {
        Path: "C:\\WINDOWS\\system32;C:\\Users\\exampleuser\\AppData\\Local\\Programs\\obsidian"
      },
      commandExists() {
        return false;
      },
      hasRunningObsidianProcess() {
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

run("writeNote falls back to filesystem when Obsidian CLI does not materialize the file", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-note-writer-fallback-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: []
      }
    };
    const note = {
      path: "08-ai-kb/10-raw/manual/Test-Note.md",
      content: `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "Test Note",
        source_url: "https://example.com/test-note",
        status: "queued"
      })}\n\n# Test Note\n`
    };

    const result = writeNote(config, note, {
      allowFilesystemFallback: true,
      preferCli: true,
      cliVerifyTimeoutMs: 0,
      runObsidian() {
        return { status: 0 };
      }
    });

    assert.equal(result.mode, "filesystem-fallback");
    assert.equal(
      fs.readFileSync(path.join(config.vaultPath, note.path), "utf8"),
      note.content
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("writeNote forwards CLI timeout and exposes timeout fallback metadata", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-note-writer-timeout-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: []
      }
    };
    const note = {
      path: "08-ai-kb/10-raw/manual/Timeout-Note.md",
      content: `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "Timeout Note",
        source_url: "https://example.com/timeout-note",
        status: "queued"
      })}\n\n# Timeout Note\n`
    };
    let receivedTimeoutMs = null;

    const result = writeNote(config, note, {
      allowFilesystemFallback: true,
      preferCli: true,
      cliRunTimeoutMs: 4321,
      resolveObsidianEnvironment() {
        return {
          cliCommand: "obsidian",
          exePath: "C:\\Users\\exampleuser\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe",
          cliMode: "registered-command",
          appRunning: true
        };
      },
      runObsidian(_config, _commandArgs, cliOptions) {
        receivedTimeoutMs = cliOptions.timeoutMs;
        const error = new Error("Obsidian CLI timed out after 4321ms: obsidian");
        error.code = "OBSIDIAN_CLI_TIMEOUT";
        throw error;
      }
    });

    assert.equal(receivedTimeoutMs, 4321);
    assert.equal(result.mode, "filesystem-fallback");
    assert.equal(result.cliAttempted, true);
    assert.equal(result.cliErrorCode, "OBSIDIAN_CLI_TIMEOUT");
    assert.match(result.cliErrorMessage, /timed out/i);
    assert.equal(
      fs.readFileSync(path.join(config.vaultPath, note.path), "utf8"),
      note.content
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("reference hub compiled_from uses wiki note paths instead of raw notes", () => {
  const compiledFrom = buildReferenceHubCompiledFrom([
    {
      path: "08-AI知识库/20-wiki/sources/A-reference-map.md"
    },
    {
      path: "08-AI知识库/20-wiki/sources/B-reference-map.md"
    },
    {
      path: "08-AI知识库/20-wiki/sources/A-reference-map.md"
    },
    {
      path: "08-AI知识库/10-raw/books/ignored.md"
    }
  ]);

  assert.deepEqual(compiledFrom, [
    "08-AI知识库/20-wiki/sources/A-reference-map.md",
    "08-AI知识库/20-wiki/sources/B-reference-map.md"
  ]);
});

run("reference hub repair extracts linked wiki notes from Book Maps section", () => {
  const body = `# Finance Book Reference Hub

## Book Maps

- [[08-AI知识库/20-wiki/sources/A-reference-map|A]]
- [[08-AI知识库/20-wiki/sources/B-reference-map|B]]

## Search Seeds

- ignored
`;

  assert.deepEqual(extractLinkedWikiPathsFromSection(body, "Book Maps"), [
    "08-AI知识库/20-wiki/sources/A-reference-map.md",
    "08-AI知识库/20-wiki/sources/B-reference-map.md"
  ]);
});

run("writeNote keeps cli mode when the CLI-created file is actually present", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-note-writer-cli-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: []
      }
    };
    const note = {
      path: "08-ai-kb/20-wiki/concepts/Test-Concept.md",
      content: `${generateFrontmatter("wiki", {
        wiki_kind: "concept",
        topic: "Test Concept",
        compiled_from: ["08-ai-kb/10-raw/manual/Test-Note.md"],
        kb_source_count: 1,
        dedup_key: "test concept::concept::title:test-concept"
      })}\n\n# Test Concept\n`
    };

    const result = writeNote(config, note, {
      allowFilesystemFallback: true,
      preferCli: true,
      cliVerifyTimeoutMs: 0,
      resolveObsidianEnvironment() {
        return {
          cliCommand: "obsidian",
          exePath: "C:\\Users\\exampleuser\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe",
          cliMode: "registered-command"
        };
      },
      forceCli: true,
      runObsidian(_config, commandArgs, cliOptions) {
        assert.equal(cliOptions.stdio, "ignore");
        const notePath = commandArgs.find((entry) => entry.startsWith("path=")).slice(5);
        const content = commandArgs.find((entry) => entry.startsWith("content=")).slice(8);
        const target = path.join(config.vaultPath, notePath);
        fs.mkdirSync(path.dirname(target), { recursive: true });
        fs.writeFileSync(target, content, "utf8");
        return { status: 0 };
      }
    });

    assert.equal(result.mode, "cli");
    assert.equal(
      fs.readFileSync(path.join(config.vaultPath, note.path), "utf8"),
      note.content
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("writeNote attempts CLI before filesystem fallback when preferCli is enabled", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-note-writer-prefer-cli-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: []
      }
    };
    const note = {
      path: "08-ai-kb/10-raw/manual/Prefer-Cli.md",
      content: `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "Prefer CLI",
        source_url: "https://example.com/prefer-cli",
        status: "queued"
      })}\n\n# Prefer CLI\n`
    };
    let cliInvoked = false;

    const result = writeNote(config, note, {
      allowFilesystemFallback: true,
      preferCli: true,
      cliVerifyTimeoutMs: 0,
      resolveObsidianEnvironment() {
        return {
          cliCommand: "obsidian",
          exePath: "C:\\Users\\exampleuser\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe",
          cliMode: "registered-command"
        };
      },
      runObsidian(_config, commandArgs) {
        cliInvoked = true;
        const notePath = commandArgs.find((entry) => entry.startsWith("path=")).slice(5);
        const content = commandArgs.find((entry) => entry.startsWith("content=")).slice(8);
        const target = path.join(config.vaultPath, notePath);
        fs.mkdirSync(path.dirname(target), { recursive: true });
        fs.writeFileSync(target, content, "utf8");
        return { status: 0 };
      }
    });

    assert.equal(cliInvoked, true);
    assert.equal(result.mode, "cli");
    assert.equal(
      fs.readFileSync(path.join(config.vaultPath, note.path), "utf8"),
      note.content
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("writeNote skips desktop executable fallback and writes directly to disk", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-note-writer-no-launch-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: ["C:\\Users\\exampleuser\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe"]
      }
    };
    const note = {
      path: "08-ai-kb/20-wiki/sources/Test-Source.md",
      content: `${generateFrontmatter("wiki", {
        wiki_kind: "source",
        topic: "Test Source",
        compiled_from: ["08-ai-kb/10-raw/manual/Test-Note.md"],
        kb_source_count: 1,
        dedup_key: "test source::source::title:test-source"
      })}\n\n# Test Source\n`
    };
    let cliInvoked = false;

    const result = writeNote(config, note, {
      allowFilesystemFallback: true,
      preferCli: true,
      resolveObsidianEnvironment() {
        return {
          cliCommand: "C:\\Users\\exampleuser\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe",
          exePath: "C:\\Users\\exampleuser\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe",
          cliMode: "desktop-executable",
          appRunning: false
        };
      },
      runObsidian() {
        cliInvoked = true;
        throw new Error("desktop executable should not be launched");
      }
    });

    assert.equal(cliInvoked, false);
    assert.equal(result.mode, "filesystem-fallback");
    assert.equal(
      fs.readFileSync(path.join(config.vaultPath, note.path), "utf8"),
      note.content
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("writeNote avoids launching a closed Obsidian app when fallback is allowed", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-note-writer-no-autostart-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: ["obsidian"],
        exeCandidates: []
      }
    };
    const note = {
      path: "08-ai-kb/20-wiki/sources/No-Autostart.md",
      content: `${generateFrontmatter("wiki", {
        wiki_kind: "source",
        topic: "No Autostart",
        compiled_from: ["08-ai-kb/10-raw/manual/Test-Note.md"],
        kb_source_count: 1,
        dedup_key: "no autostart::source::title:no-autostart"
      })}\n\n# No Autostart\n`
    };
    let cliInvoked = false;

    const result = writeNote(config, note, {
      allowFilesystemFallback: true,
      preferCli: true,
      resolveObsidianEnvironment() {
        return {
          cliCommand: "obsidian",
          exePath: "C:\\Users\\exampleuser\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe",
          cliMode: "registered-command",
          appRunning: false
        };
      },
      runObsidian() {
        cliInvoked = true;
        throw new Error("closed Obsidian app should not be auto-launched");
      }
    });

    assert.equal(cliInvoked, false);
    assert.equal(result.mode, "filesystem-fallback");
    assert.equal(
      fs.readFileSync(path.join(config.vaultPath, note.path), "utf8"),
      note.content
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
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
    notePaths.includes(getStaleNotesPath(config.machineRoot)),
    "Missing stale notes view"
  );
  assert.ok(
    notePaths.includes(getOpenQuestionsPath(config.machineRoot)),
    "Missing open questions view"
  );
  assert.ok(
    notePaths.includes(getSourcesByTopicPath(config.machineRoot)),
    "Missing sources by topic view"
  );

  const dashboardNote = plan.notes.find(
    (note) => note.path === getDashboardPath(config.machineRoot)
  );
  assert.ok(dashboardNote);
  assert.match(dashboardNote.content, /SORT kb_date DESC/);
  assert.match(dashboardNote.content, /## Stats/);
  assert.match(dashboardNote.content, /## Trading Fast Lane/);
  assert.match(dashboardNote.content, /## Maintenance Commands/);
  assert.match(dashboardNote.content, /Trading Card Stack/);
  assert.match(dashboardNote.content, /Political Economy Sources/);
  assert.match(dashboardNote.content, /Recent Mentor Sessions/);

  const kbHomeNote = plan.notes.find(
    (note) => note.path.endsWith("/KB Home.md")
  );
  assert.ok(kbHomeNote);
  assert.match(kbHomeNote.content, /01-Stale Notes/);
  assert.match(kbHomeNote.content, /20-wiki\/_index/);
  assert.match(kbHomeNote.content, /20-wiki\/_log/);
});

run("trading suite plan keeps the expected refresh order", () => {
  const fullPlan = buildTradingRefreshPlan();
  const noHealthPlan = buildTradingRefreshPlan({
    includeHealthCheck: false
  });

  assert.deepEqual(
    fullPlan.map((step) => step.id),
    [
      "refresh-oneil-core-notes",
      "refresh-trading-core-notes",
      "refresh-trading-extension-notes",
      "refresh-trading-synthesis-notes",
      "refresh-trading-playbook-notes",
      "refresh-trading-template-notes",
      "refresh-trading-risk-notes",
      "refresh-trading-card-notes",
      "refresh-wiki-views",
      "health-check"
    ]
  );
  assert.equal(noHealthPlan.at(-1).id, "refresh-wiki-views");
});

run("political economy suite plan keeps the expected refresh order", () => {
  const fullPlan = buildPoliticalEconomyRefreshPlan();
  const noHealthPlan = buildPoliticalEconomyRefreshPlan({
    includeHealthCheck: false
  });

  assert.deepEqual(
    fullPlan.map((step) => step.id),
    ["process-political-economy-books", "refresh-wiki-views", "health-check"]
  );
  assert.equal(noHealthPlan.at(-1).id, "refresh-wiki-views");
});

run("x source registry extracts handles from profile and status URLs", () => {
  assert.equal(extractXHandleFromUrl("https://x.com/Ariston_Macro"), "Ariston_Macro");
  assert.equal(
    extractXHandleFromUrl("https://x.com/Ariston_Macro/status/2041091494116003853"),
    "Ariston_Macro"
  );
  assert.equal(extractXHandleFromUrl("https://twitter.com/karpathy/status/123"), "karpathy");
  assert.equal(extractXHandleFromUrl("https://example.com/not-x"), "");
});

run("x source registry prompts for unknown handles and recognizes allowlisted authors", () => {
  const registry = {
    version: 1,
    updated_at: "2026-04-06T00:00:00+08:00",
    default_policy: {
      media_policy: "remote_only",
      promoted_bucket: "08-AI鐭ヨ瘑搴?10-raw/web/x-promoted",
      index_bucket: "08-AI鐭ヨ瘑搴?10-raw/web/x-index",
      promotion_rules: {
        promote_to_raw: ["call_summary"],
        index_only: ["chart_only"],
        ignore: ["pure_engagement"]
      }
    },
    authors: [createDefaultXAuthorEntry({ handle: "Ariston_Macro", addedAt: "2026-04-06T00:00:00+08:00" })]
  };

  const known = inspectXSourceUrl("https://x.com/Ariston_Macro/status/1", registry);
  const unknown = inspectXSourceUrl("https://x.com/NewMacroDesk/status/2", registry);

  assert.equal(known.isAllowlisted, true);
  assert.equal(known.shouldPromptToWhitelist, false);
  assert.equal(unknown.isAllowlisted, false);
  assert.equal(unknown.shouldPromptToWhitelist, true);
  assert.equal(unknown.handle, "NewMacroDesk");
});

run("x source registry upsert stays normalized and sorted", () => {
  const registry = {
    version: 1,
    updated_at: "2026-04-06T00:00:00+08:00",
    default_policy: {},
    authors: [createDefaultXAuthorEntry({ handle: "z_handle", addedAt: "2026-04-06T00:00:00+08:00" })]
  };

  const next = upsertXAuthorEntry(
    registry,
    createDefaultXAuthorEntry({
      handle: "@AlphaDesk/",
      addedAt: "2026-04-06T00:00:00+08:00"
    })
  );

  assert.deepEqual(
    next.authors.map((item) => item.handle),
    ["AlphaDesk", "z_handle"]
  );
});

run("x-index import can filter specific posts by URL and limit", () => {
  const result = {
    x_posts: [
      { post_url: "https://x.com/LinQingV/status/2041135310852235487" },
      { post_url: "https://x.com/LinQingV/status/2041015554740543812" },
      { post_url: "https://x.com/LinQingV/status/2041154721172631584" }
    ]
  };

  const selectedByUrl = selectXPostsForPromotion(result, {
    postUrls: ["https://x.com/LinQingV/status/2041015554740543812/"]
  });
  const selectedByLimit = selectXPostsForPromotion(result, { limit: 2 });

  assert.equal(selectedByUrl.length, 1);
  assert.equal(
    selectedByUrl[0].post_url,
    "https://x.com/LinQingV/status/2041015554740543812"
  );
  assert.deepEqual(
    selectedByLimit.map((item) => item.post_url),
    [
      "https://x.com/LinQingV/status/2041135310852235487",
      "https://x.com/LinQingV/status/2041015554740543812"
    ]
  );
});

run("x-index import builds promoted raw note inside x-promoted bucket", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-x-index-note-build-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };
    const registry = {
      version: 1,
      updated_at: "2026-04-06T21:04:36+08:00",
      default_policy: {
        media_policy: "remote_only",
        index_bucket: "08-ai-kb/10-raw/web/x-index",
        promoted_bucket: "08-ai-kb/10-raw/web/x-promoted",
        promotion_rules: {
          promote_to_raw: ["important_thread"],
          index_only: ["chart_only"],
          ignore: ["pure_engagement"]
        }
      },
      authors: [createDefaultXAuthorEntry({ handle: "LinQingV", addedAt: "2026-04-06T21:04:36+08:00" })]
    };
    const result = {
      request: {
        topic: "LinQingV auto analysis",
        analysis_time: "2026-04-06T13:40:00+00:00",
        account_allowlist: ["LinQingV"],
        keywords: ["BYD", "SAIC", "Fuyao Glass"],
        phrase_clues: [],
        entity_clues: [],
        include_threads: false,
        include_images: true
      }
    };
    const post = {
      post_url: "https://x.com/LinQingV/status/2041135310852235487",
      author_handle: "LinQingV",
      author_display_name: "LinQingV",
      posted_at: "2026-04-06T12:45:55+00:00",
      post_text_raw: "auto analysis raw text",
      post_summary: "auto analysis summary",
      combined_summary: "Post: auto analysis summary",
      discovery_reason: "allowlist_profile_recent:@LinQingV|browser_session_profile_recent",
      access_mode: "browser_session",
      session_source: "remote_debugging",
      session_status: "ready",
      social_rank: 50,
      artifact_manifest: [
        {
          role: "root_post_screenshot",
          path: "C:\\tmp\\root.png",
          source_url: "https://x.com/LinQingV/status/2041135310852235487",
          media_type: "screenshot"
        }
      ],
      media_items: [
        {
          media_type: "image",
          source_url: "https://pbs.twimg.com/media/example.jpg",
          local_artifact_path: "C:\\tmp\\media-1.png",
          image_relevance_to_post: "low",
          ocr_status: "unavailable"
        }
      ]
    };

    const note = buildPromotedXRawNote(config, result, post, { registry });

    assert.equal(
      note.path,
      "08-ai-kb/10-raw/web/x-promoted/LinQingV-2041135310852235487.md"
    );
    assert.match(note.title, /LinQingV/);
    assert.match(note.content, /source_type: "web_article"/);
    assert.match(note.content, /topic: "LinQingV auto analysis"/);
    assert.match(note.content, /## Main Post/);
    assert.match(note.content, /## Media Artifacts/);
    assert.match(note.content, /auto analysis raw text/);
    assert.match(note.content, /Allowlist status: allowlisted/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("x-index import writes promoted raw notes with queued status", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-x-index-note-write-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };
    const registry = {
      version: 1,
      updated_at: "2026-04-06T21:04:36+08:00",
      default_policy: {
        media_policy: "remote_only",
        index_bucket: "08-ai-kb/10-raw/web/x-index",
        promoted_bucket: "08-ai-kb/10-raw/web/x-promoted",
        promotion_rules: {
          promote_to_raw: ["important_thread"],
          index_only: ["chart_only"],
          ignore: ["pure_engagement"]
        }
      },
      authors: [createDefaultXAuthorEntry({ handle: "LinQingV", addedAt: "2026-04-06T21:04:36+08:00" })]
    };
    const result = {
      request: {
        topic: "LinQingV auto analysis",
        analysis_time: "2026-04-06T13:40:00+00:00",
        account_allowlist: ["LinQingV"],
        keywords: ["BYD", "SAIC", "Fuyao Glass"],
        include_threads: false,
        include_images: true
      },
      x_posts: [
        {
          post_url: "https://x.com/LinQingV/status/2041135310852235487",
          author_handle: "LinQingV",
          author_display_name: "LinQingV",
          posted_at: "2026-04-06T12:45:55+00:00",
          post_text_raw: "BYD SAIC Fuyao analysis",
          post_summary: "auto analysis summary",
          combined_summary: "Post: auto analysis summary",
        },
        {
          post_url: "https://x.com/LinQingV/status/2041015554740543812",
          author_handle: "LinQingV",
          author_display_name: "LinQingV",
          posted_at: "2026-04-06T04:33:22+00:00",
          post_text_raw: "shipping capacity note",
          post_summary: "shipping comparison summary",
          combined_summary: "Post: shipping comparison summary",
        }
      ]
    };

    const writes = importXIndexPosts(config, result, {
      registry,
      postIds: ["2041135310852235487"],
      preferCli: false,
      allowFilesystemFallback: true
    });

    assert.equal(writes.length, 1);
    assert.equal(writes[0].action, "create");

    const notePath = path.join(config.vaultPath, writes[0].path);
    const content = fs.readFileSync(notePath, "utf8");
    const frontmatter = parseFrontmatter(content);
    assert.doesNotThrow(() => validateRawFrontmatter(frontmatter));
    assert.equal(frontmatter.status, "queued");
    assert.equal(frontmatter.topic, "LinQingV auto analysis");
    assert.match(content, /## Request Context/);
    assert.match(content, /BYD SAIC Fuyao analysis/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify sidecar builds stable topic paths", () => {
  const paths = buildGraphifyTopicPaths("C:\\repo\\obsidian-kb-local", "涓浗姹借溅鍑烘捣閾撅細姣斾簹杩€佷笂姹姐€佺鑰€鐜荤拑");
  assert.match(paths.sidecarRoot, /graphify-sidecar/i);
  assert.match(paths.inputRoot, /input$/i);
  assert.match(paths.graphifyOutRoot, /graphify-out$/i);
  assert.ok(paths.slug.length > 0);
});

run("graphify topic workspace discovery normalizes empty manifest topics", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-workspaces-"));

  try {
    const archivedRoot = path.join(tempRoot, "graphify-sidecar", "_archived");
    const sidecarRoot = path.join(tempRoot, "graphify-sidecar", "untitled-note");
    fs.mkdirSync(archivedRoot, { recursive: true });
    fs.mkdirSync(path.join(sidecarRoot, "graphify-out"), { recursive: true });
    fs.writeFileSync(
      path.join(archivedRoot, "ignored.txt"),
      "ignore me",
      "utf8"
    );
    fs.writeFileSync(
      path.join(sidecarRoot, "manifest.json"),
      JSON.stringify(
        {
          topic: '"',
          slug: "untitled-note",
          selectionMode: "keyword-fallback"
        },
        null,
        2
      ),
      "utf8"
    );

    const workspaces = discoverGraphifyTopicWorkspaces(tempRoot);
    assert.equal(workspaces.length, 1);
    assert.equal(workspaces[0].topic, "untitled-note");
    assert.equal(normalizeGraphifyTopicLabel('"', "fallback"), "fallback");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify sidecar extracts existing artifact paths from markdown", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-artifacts-"));
  try {
    const artifactPath = path.join(tempRoot, "artifact.png");
    fs.writeFileSync(artifactPath, "fake", "utf8");
    const content = `- root_post_screenshot: source=https://x.com/example/status/1 | path=${artifactPath}`;
    const found = extractArtifactPathsFromMarkdown(content);
    assert.deepEqual(found, [artifactPath]);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify sidecar stages topic raw and wiki notes into sidecar workspace", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-stage-"));

  try {
    const { config, rawPath } = createCompileFixture(tempRoot);
    const wikiRoot = path.join(config.vaultPath, config.machineRoot, "20-wiki", "sources");
    fs.mkdirSync(wikiRoot, { recursive: true });
    fs.writeFileSync(
      path.join(wikiRoot, "Karpathy-Source.md"),
      buildWikiFixture({
        wiki_kind: "source",
        topic: "LLM Knowledge Bases",
        compiled_from: [rawPath],
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04",
        kb_source_count: 1,
        dedup_key: "llm knowledge bases::source::https://example.com/article",
        title: "Karpathy Source",
        body: "## Summary\n\nA source summary."
      }),
      "utf8"
    );

    const { paths, staged } = stageGraphifyTopicCorpus(config, "LLM Knowledge Bases");
    assert.equal(staged.counts.raw, 1);
    assert.equal(staged.counts.wiki, 1);
    assert.ok(fs.existsSync(paths.manifestPath));
    assert.ok(fs.existsSync(paths.runbookPath));
    assert.ok(staged.rawNotes[0].destination.includes(`${path.sep}input${path.sep}raw${path.sep}`));
    assert.ok(staged.wikiNotes[0].destination.includes(`${path.sep}input${path.sep}wiki${path.sep}`));

    const vaultNote = buildGraphifyVaultNote(config, "LLM Knowledge Bases", paths);
    assert.match(vaultNote.path, /07-Graph Insights/i);
    assert.match(vaultNote.content, /graphify-out/i);
    assert.match(buildGraphifySidecarReadme(staged, paths), /Suggested command/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify network index maps staged source files back to vault note paths", () => {
  const sourceMap = buildSourceFileToVaultPathMap({
    rawNotes: [
      {
        relativePath: "08-AI鐭ヨ瘑搴?10-raw/books/Test-Book.md"
      }
    ],
    wikiNotes: [
      {
        relativePath: "08-AI鐭ヨ瘑搴?20-wiki/concepts/Test-Concept.md",
        wikiKind: "concept"
      }
    ]
  });

  assert.equal(sourceMap.get("raw/Test-Book.md"), "08-AI鐭ヨ瘑搴?10-raw/books/Test-Book.md");
  assert.equal(
    sourceMap.get("wiki/concept/Test-Concept.md"),
    "08-AI鐭ヨ瘑搴?20-wiki/concepts/Test-Concept.md"
  );
});

run("graphify contract summarizes schema, coverage, and query recipes", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-contract-"));

  try {
    const paths = buildGraphifyTopicPaths(tempRoot, "Wyckoff");
    fs.mkdirSync(paths.graphifyOutRoot, { recursive: true });

    fs.writeFileSync(
      paths.manifestPath,
      JSON.stringify(
        {
          topic: "Wyckoff",
          selectionMode: "profile-whitelist",
          fallbackProfileId: "wyckoff",
          rawNotes: [
            {
              relativePath: "08-ai-kb/10-raw/books/Wyckoff-Book.md"
            }
          ],
          wikiNotes: [
            {
              relativePath: "08-ai-kb/20-wiki/concepts/Wyckoff-methodology.md",
              wikiKind: "concept"
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    fs.writeFileSync(
      path.join(paths.graphifyOutRoot, "graph.json"),
      JSON.stringify(
        {
          nodes: [
            {
              id: "raw_book",
              label: "Wyckoff Book",
              file_type: "paper",
              source_file: "raw/Wyckoff-Book.md",
              community: 0
            },
            {
              id: "wiki_method",
              label: "Wyckoff methodology",
              file_type: "document",
              source_file: "wiki/concept/Wyckoff-methodology.md",
              community: 1
            }
          ],
          links: [
            {
              source: "wiki_method",
              target: "raw_book",
              relation: "compiled_from",
              confidence: "EXTRACTED",
              confidence_score: 1
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    fs.writeFileSync(
      path.join(paths.graphifyOutRoot, "markdown-extraction.json"),
      JSON.stringify(
        {
          topic: "Wyckoff",
          nodes: [{}, {}],
          edges: [{}]
        },
        null,
        2
      ),
      "utf8"
    );
    fs.writeFileSync(path.join(paths.graphifyOutRoot, "GRAPH_REPORT.md"), "# Report\n", "utf8");

    const contract = buildGraphContract(paths);
    assert.equal(contract.topic, "Wyckoff");
    assert.equal(contract.graphCounts.nodes, 2);
    assert.equal(contract.graphCounts.edges, 1);
    assert.equal(contract.manifestCoverage.missingStagedFiles.length, 0);
    assert.ok(contract.relationTypes.some((row) => row.name === "compiled_from"));
    assert.equal(contract.queryRecipes.length, 3);

    const markdown = buildGraphContractMarkdown(paths, {
      contract,
      lint: lintGraphArtifacts(paths, { contract })
    });
    assert.match(markdown, /## Graph Contract/);
    assert.match(markdown, /### Query Entry/);
    assert.match(markdown, /query-wiki\.mjs/);

    const artifacts = writeGraphContractArtifacts(paths, {
      contract,
      lint: lintGraphArtifacts(paths, { contract })
    });
    assert.equal(fs.existsSync(artifacts.contractPath), true);
    assert.equal(fs.existsSync(artifacts.lintPath), true);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify lint flags schema drift and missing staged coverage", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-lint-"));

  try {
    const paths = buildGraphifyTopicPaths(tempRoot, "CAN SLIM");
    fs.mkdirSync(paths.graphifyOutRoot, { recursive: true });

    fs.writeFileSync(
      paths.manifestPath,
      JSON.stringify(
        {
          topic: "CAN SLIM",
          selectionMode: "profile-whitelist",
          fallbackProfileId: "can-slim",
          rawNotes: [
            {
              relativePath: "08-ai-kb/10-raw/books/CAN-SLIM-Book.md"
            }
          ],
          wikiNotes: [
            {
              relativePath: "08-ai-kb/20-wiki/concepts/CAN-SLIM.md",
              wikiKind: "concept"
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    fs.writeFileSync(
      path.join(paths.graphifyOutRoot, "graph.json"),
      JSON.stringify(
        {
          nodes: [
            {
              id: "wiki_concept",
              label: "CAN SLIM",
              file_type: "document",
              source_file: "wiki/concept/CAN-SLIM.md",
              community: 0
            }
          ],
          links: [
            {
              source: "wiki_concept",
              target: "missing_raw",
              relation: "unknown_relation",
              confidence: "EXTRACTED",
              confidence_score: 2
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    fs.writeFileSync(
      path.join(paths.graphifyOutRoot, "markdown-extraction.json"),
      JSON.stringify(
        {
          topic: "CAN SLIM",
          nodes: [{}],
          edges: [{}]
        },
        null,
        2
      ),
      "utf8"
    );

    const lint = lintGraphArtifacts(paths);
    assert.equal(lint.status, "fail");
    assert.ok(lint.issues.some((entry) => entry.code === "edge-endpoint-not-found"));
    assert.ok(lint.issues.some((entry) => entry.code === "edge-unknown-relation"));
    assert.ok(lint.issues.some((entry) => entry.code === "missing-staged-graph-nodes"));
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graph topic status note summarizes all sidecar topics", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graph-topic-status-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };
    const canSlimRoot = path.join(tempRoot, "graphify-sidecar", "CAN-SLIM");
    const draftRoot = path.join(tempRoot, "graphify-sidecar", "untitled-note");
    fs.mkdirSync(path.join(canSlimRoot, "graphify-out"), { recursive: true });
    fs.mkdirSync(path.join(draftRoot, "graphify-out"), { recursive: true });

    fs.writeFileSync(
      path.join(canSlimRoot, "manifest.json"),
      JSON.stringify(
        {
          topic: "CAN SLIM",
          slug: "CAN-SLIM",
          selectionMode: "profile-whitelist"
        },
        null,
        2
      ),
      "utf8"
    );
    fs.writeFileSync(
      path.join(canSlimRoot, "graphify-out", "graph-contract.json"),
      JSON.stringify(
        {
          topic: "CAN SLIM",
          selectionMode: "profile-whitelist",
          graphCounts: {
            nodes: 12,
            edges: 18,
            communities: 3
          }
        },
        null,
        2
      ),
      "utf8"
    );
    fs.writeFileSync(
      path.join(canSlimRoot, "graphify-out", "graph-lint.json"),
      JSON.stringify(
        {
          topic: "CAN SLIM",
          status: "pass",
          errorCount: 0,
          warningCount: 0,
          issues: []
        },
        null,
        2
      ),
      "utf8"
    );
    fs.writeFileSync(path.join(canSlimRoot, "graphify-out", "graph.json"), "{}", "utf8");

    fs.writeFileSync(
      path.join(draftRoot, "manifest.json"),
      JSON.stringify(
        {
          topic: '"',
          slug: "untitled-note",
          selectionMode: "keyword-fallback"
        },
        null,
        2
      ),
      "utf8"
    );

    const statusRows = discoverGraphifyTopicWorkspaces(tempRoot).map(readGraphifyWorkspaceStatus);
    assert.equal(statusRows.length, 2);
    assert.ok(statusRows.some((row) => row.topic === "CAN SLIM" && row.status === "pass"));
    assert.ok(statusRows.some((row) => row.topic === "untitled-note" && row.status === "missing-graph"));

    const note = buildGraphTopicStatusContent(config, {
      timestamp: "2026-04-08T10:00:00+08:00"
    });
    assert.match(note, /Graph Topic Status/);
    assert.match(note, /CAN SLIM/);
    assert.match(note, /missing-graph/);
    assert.match(note, /Graph Insights - CAN-SLIM/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify network index builds clickable hub and bridge sections", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-network-index-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };
    const paths = buildGraphifyTopicPaths(tempRoot, "Wyckoff");
    fs.mkdirSync(paths.graphifyOutRoot, { recursive: true });

    fs.writeFileSync(
      paths.manifestPath,
      JSON.stringify(
        {
          selectionMode: "profile-whitelist",
          fallbackProfileId: "wyckoff",
          rawNotes: [
            {
              relativePath: "08-ai-kb/10-raw/books/Wyckoff-Book.md"
            }
          ],
          wikiNotes: [
            {
              relativePath: "08-ai-kb/20-wiki/concepts/Wyckoff-methodology.md",
              wikiKind: "concept"
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    fs.writeFileSync(
      path.join(paths.graphifyOutRoot, "graph.json"),
      JSON.stringify(
        {
          nodes: [
            {
              id: "raw_book",
              label: "Wyckoff Book",
              source_file: "raw/Wyckoff-Book.md",
              community: 0
            },
            {
              id: "wiki_method",
              label: "Wyckoff methodology",
              source_file: "wiki/concept/Wyckoff-methodology.md",
              community: 1
            }
          ],
          links: [
            {
              source: "raw_book",
              target: "wiki_method",
              relation: "conceptually_related_to",
              confidence: "INFERRED",
              confidence_score: 0.82
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    const note = buildGraphNetworkIndexNote(config, "Wyckoff", paths);
    assert.match(note.path, /08-Network Index/i);
    assert.match(note.content, /\[\[08-ai-kb\/10-raw\/books\/Wyckoff-Book.md\|Wyckoff Book\]\]/);
    assert.match(note.content, /\[\[08-ai-kb\/20-wiki\/concepts\/Wyckoff-methodology.md\|Wyckoff methodology\]\]/);
    assert.match(note.content, /Layer 1: Bridge Links/);
    assert.match(note.content, /Layer 3: Local Neighborhoods/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify activation trace builds hop-based propagation paths", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-network-trace-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };
    const paths = buildGraphifyTopicPaths(tempRoot, "CAN SLIM");
    fs.mkdirSync(paths.graphifyOutRoot, { recursive: true });

    fs.writeFileSync(
      paths.manifestPath,
      JSON.stringify(
        {
          selectionMode: "profile-whitelist",
          fallbackProfileId: "can-slim",
          rawNotes: [
            {
              relativePath: "08-ai-kb/10-raw/books/Book-A.md"
            }
          ],
          wikiNotes: [
            {
              relativePath: "08-ai-kb/20-wiki/concepts/Concept-B.md",
              wikiKind: "concept"
            },
            {
              relativePath: "08-ai-kb/20-wiki/entities/Entity-C.md",
              wikiKind: "entity"
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    fs.writeFileSync(
      path.join(paths.graphifyOutRoot, "graph.json"),
      JSON.stringify(
        {
          nodes: [
            { id: "a", label: "Book A", source_file: "raw/Book-A.md", community: 0 },
            { id: "b", label: "Concept B", source_file: "wiki/concept/Concept-B.md", community: 0 },
            { id: "c", label: "Entity C", source_file: "wiki/entity/Entity-C.md", community: 1 }
          ],
          links: [
            {
              source: "a",
              target: "b",
              relation: "compiled_from",
              confidence: "EXTRACTED",
              confidence_score: 1
            },
            {
              source: "b",
              target: "c",
              relation: "conceptually_related_to",
              confidence: "INFERRED",
              confidence_score: 0.82
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    const note = buildGraphActivationTraceNote(config, "CAN SLIM", paths);
    assert.match(note.path, /09-Network Trace/i);
    assert.match(note.content, /Seed Activation/);
    assert.match(note.content, /Two-hop spread/);
    assert.match(note.content, /\[\[08-ai-kb\/10-raw\/books\/Book-A.md\|Book A\]\] -> \[\[08-ai-kb\/20-wiki\/concepts\/Concept-B.md\|Concept B\]\] -> \[\[08-ai-kb\/20-wiki\/entities\/Entity-C.md\|Entity C\]\]/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("trading psychology mentor prompt injects query, journal, and note context", () => {
  const prompt = buildTradingPsychologyMentorPrompt(
    "Q={{QUERY}}\nT={{TOPIC}}\nJ={{JOURNAL_CONTEXT}}\nN={{NOTE_CONTEXT}}",
    {
      query: "我今天追高了",
      topic: "trading psychology",
      journalContext: "上午止损后马上想追回。",
      noteContext: "### Note 1: 持续一贯是一种心态"
    }
  );

  assert.match(prompt, /我今天追高了/);
  assert.match(prompt, /trading psychology/);
  assert.match(prompt, /上午止损后马上想追回/);
  assert.match(prompt, /持续一贯是一种心态/);
});

run("trading psychology mentor session note builds mentor view note path", () => {
  const note = buildTradingPsychologyMentorSessionNote(
    {
      machineRoot: "08-AI知识库"
    },
    {
      query: "我追高后止损又追回",
      templateLabel: "盘中模板",
      journalContext: "连续两笔亏损后情绪急躁。",
      answer: "先暂停，再看失效条件。",
      selectedNotes: []
    }
  );

  assert.match(note.path, /30-views\/10-Trading Psychology Mentor\/01-Sessions\//);
  assert.match(note.content, /盘中模板/);
  assert.match(note.content, /Mentor Response/);
  assert.match(note.content, /先暂停，再看失效条件/);
});

run("trading psychology mentor arg parser enforces write-session only with execute", () => {
  assert.throws(
    () => parseTradingPsychologyMentorArgs(["--query", "test", "--write-session"]),
    /requires --execute/
  );
});

run("trading psychology mentor session note records provider execution context", () => {
  const note = buildTradingPsychologyMentorSessionNote(
    {
      machineRoot: "08-AI知识库"
    },
    {
      query: "我追高后止损又追回",
      templateLabel: "盘中模板",
      journalContext: "连续两笔亏损后情绪急躁。",
      answer: "先暂停，再看失效条件。",
      responseMode: "local-fallback",
      providerRoute:
        "openai | gpt-5.4 | responses | https://api.openai.com/v1 (route:codex-exec-fallback, auth-mode:chatgpt, api-key:missing)",
      providerEndpoint: "local-fallback",
      fallbackReason: "Responses API returned no textual output",
      selectedNotes: []
    }
  );

  assert.match(note.content, /Execution Context/);
  assert.match(note.content, /Response mode: local-fallback/);
  assert.match(note.content, /route:codex-exec-fallback/);
  assert.match(note.content, /Fallback reason: Responses API returned no textual output/);
});

run("trading psychology mentor arg parser allows template without explicit query", () => {
  const parsed = parseTradingPsychologyMentorArgs(["--template", "premarket", "--dry-run"]);
  assert.equal(parsed.template, "premarket");
  assert.equal(parsed.query, "");
});

run("trading psychology mentor arg parser accepts context-note", () => {
  const parsed = parseTradingPsychologyMentorArgs([
    "--query",
    "test",
    "--context-note",
    "08-AI知识库/30-views/10-Trading Psychology Mentor/02-Templates/Trading Psychology Template - 盘中模板.md"
  ]);
  assert.equal(
    parsed.contextNote,
    "08-AI知识库/30-views/10-Trading Psychology Mentor/02-Templates/Trading Psychology Template - 盘中模板.md"
  );
});

run("trading psychology mentor fallback response names chase and revenge patterns", () => {
  const response = buildTradingPsychologyMentorFallbackResponse({
    query: "我追高后止损又追回",
    journalContext: "高开冲高追单，止损后因为不甘心又追回，盘中一直盯盈亏。"
  });

  assert.match(response, /FOMO/);
  assert.match(response, /报复性交易/);
  assert.match(response, /What You Did Well/);
  assert.match(response, /Next Drill/);
});

run("trading psychology mentor templates resolve and build template notes", () => {
  const template = resolveTradingPsychologyMentorTemplate("premarket");
  assert.equal(template.label, "盘前模板");

  const note = buildTradingPsychologyTemplateNote(
    {
      machineRoot: "08-AI知识库"
    },
    "postmarket"
  );
  assert.match(note.path, /10-Trading Psychology Mentor\/02-Templates\//);
  assert.match(note.content, /盘后模板/);
  assert.match(note.content, /明日修正/);
});

run("stdin text decoder handles utf16le chinese content from powershell pipes", () => {
  const sample = "盘中情景：高开冲高后快速回落。";
  const encoded = Buffer.from(sample, "utf16le");
  assert.equal(decodeUnknownText(encoded), sample);
});

run("trading psychology mentor fallback prefers early-add diagnosis for calm starter positions", () => {
  const response = buildTradingPsychologyMentorFallbackResponse({
    query:
      "请重点评估：在逻辑成立但确认未完全完成时，我先开极小底仓、克制不追、等待确认后再决定是否加仓，这样的盘中执行是否合格？",
    journalContext:
      "国电南瑞和中国西电逻辑成立，我先各开了100股底仓，整体冷静，没有报复性冲动，更像轻微FOMO和想提前加仓的冲动。"
  });

  assert.match(response, /过早加仓冲动/);
  assert.match(response, /底仓/);
  assert.doesNotMatch(response, /报复性交易：亏损和不甘心/);
});
run("graphify topic fallback scores notes by keyword relevance", () => {
  const note = {
    title: "Momentum Trading Breakouts",
    relativePath: "08-AI鐭ヨ瘑搴?10-raw/books/Momentum-Trading.md",
    content: "Momentum trading setups, breakout entries, and trend continuation rules.",
    frontmatter: {
      topic: "breakout trend trading"
    }
  };

  const scored = scoreTopicSearchNote(note, "momentum trading");
  assert.ok(scored.score > 0);
  assert.deepEqual(scored.matchedTokens.sort(), ["momentum", "trading"]);
});

run("graphify momentum trading profile penalizes macro-only momentum mentions", () => {
  const note = {
    title: "21st Century Monetary Policy",
    relativePath: "08-AI鐭ヨ瘑搴?10-raw/books/21st-Century-Monetary-Policy.md",
    content:
      "Inflation expectations developed momentum and the Federal Reserve had to respond with tighter policy.",
    frontmatter: {
      topic: "Federal Reserve inflation history"
    }
  };

  const scored = scoreTopicSearchNote(note, "momentum trading");
  assert.equal(scored.score, 0);
});

run("graphify wyckoff profile recognizes core method notes", () => {
  const note = {
    title: "Wyckoff methodology",
    relativePath: "08-AI鐭ヨ瘑搴?20-wiki/concepts/Wyckoff-methodology.md",
    content: "Supply and demand, cause and effect, effort and result, accumulation, distribution.",
    frontmatter: {
      topic: "Wyckoff 1 ENG DIGITAL"
    }
  };

  const scored = scoreTopicSearchNote(note, "Wyckoff");
  assert.ok(scored.score > 0);
});

run("graphify trading psychology profile recognizes core mindset notes", () => {
  const note = {
    title: "Trading Psychology Core Mindset",
    relativePath: "08-ai-kb/20-wiki/concepts/Trading-Psychology-Core-Mindset.md",
    content: "Accept uncertainty, probability thinking, journaling, and core mindset discipline.",
    frontmatter: {
      topic: "Trading Psychology Core Mindset"
    }
  };

  const scored = scoreTopicSearchNote(note, "trading psychology");
  assert.ok(scored.score > 0);
});

run("graphify ai knowledge workflows profile recognizes workflow notes", () => {
  const note = {
    title: "Karpathy LLM Wiki 绾跨▼涓紑濮嬫敹鏁涚殑 4 涓?workflow 鍒ゆ柇",
    relativePath: "08-AI鐭ヨ瘑搴?20-wiki/sources/Karpathy-LLM-Wiki-绾跨▼涓紑濮嬫敹鏁涚殑-4-涓?workflow-鍒ゆ柇.md",
    content:
      "This note covers the LLM wiki workflow, Obsidian frontend, query/writeback, and docs-to-entry permission loop.",
    frontmatter: {
      topic: "AI knowledge workflows"
    }
  };

  const scored = scoreTopicSearchNote(note, "AI knowledge workflows");
  assert.ok(scored.score > 0);
});

run("graphify ai knowledge workflows profile penalizes investing workflow notes", () => {
  const note = {
    title: "Using ChatGPT as a support tool for investing workflows",
    relativePath: "08-AI鐭ヨ瘑搴?20-wiki/concepts/Using-ChatGPT-as-a-support-tool-for-investing-workflows.md",
    content:
      "This note is about investing workflows, portfolio support, and AI-assisted decision making in markets.",
    frontmatter: {
      topic: "investing workflows"
    }
  };

  const scored = scoreTopicSearchNote(note, "AI knowledge workflows");
  assert.equal(scored.score, 0);
});

run("graphify sidecar falls back to keyword selection when exact topic misses", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-fallback-"));

  try {
    const { config } = createCompileFixture(tempRoot);
    const rawBooksDir = path.join(config.vaultPath, config.machineRoot, "10-raw", "books");
    const wikiConceptDir = path.join(config.vaultPath, config.machineRoot, "20-wiki", "concepts");
    fs.mkdirSync(rawBooksDir, { recursive: true });
    fs.mkdirSync(wikiConceptDir, { recursive: true });

    const rawPath = path.join(rawBooksDir, "Momentum-Playbook.md");
    const rawFrontmatter = generateFrontmatter("raw", {
      source_type: "epub",
      topic: "Breakout Trend Following",
      source_url: "file:///books/momentum-playbook.epub",
      captured_at: "2026-04-04T10:00:00+08:00",
      kb_date: "2026-04-04",
      status: "compiled"
    });
    fs.writeFileSync(
      rawPath,
      `${rawFrontmatter}

# Momentum Playbook

Momentum trading focuses on breakout continuation and trend strength.
`,
      "utf8"
    );

    const wikiPath = path.join(wikiConceptDir, "Momentum-Concept.md");
    fs.writeFileSync(
      wikiPath,
      buildWikiFixture({
        wiki_kind: "concept",
        topic: "Breakout Trend Following",
        compiled_from: [`${config.machineRoot}/10-raw/books/Momentum-Playbook.md`],
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04",
        kb_source_count: 1,
        dedup_key: "breakout trend following::concept::title:momentum concept",
        title: "Momentum Concept",
        body: "Momentum trading combines relative strength, breakout confirmation, and risk control."
      }),
      "utf8"
    );

    const { staged } = stageGraphifyTopicCorpus(config, "momentum trading");
    assert.equal(staged.selectionMode, "profile-whitelist");
    assert.equal(staged.fallbackProfileId, "momentum-trading");
    assert.equal(staged.counts.raw, 1);
    assert.equal(staged.counts.wiki, 1);
    assert.match(
      buildGraphifySidecarReadme(staged, buildGraphifyTopicPaths(config.projectRoot, "momentum trading")),
      /profile-whitelist/
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify sidecar reset clears stale staged files before restaging", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-graphify-reset-"));

  try {
    const paths = buildGraphifyTopicPaths(tempRoot, "Momentum Trading");
    fs.mkdirSync(paths.rawRoot, { recursive: true });
    fs.mkdirSync(paths.wikiRoot, { recursive: true });
    fs.mkdirSync(paths.graphifyOutRoot, { recursive: true });
    fs.writeFileSync(path.join(paths.rawRoot, "stale.md"), "stale", "utf8");
    fs.writeFileSync(path.join(paths.wikiRoot, "stale.md"), "stale", "utf8");
    fs.writeFileSync(path.join(paths.graphifyOutRoot, "graph.json"), "{}", "utf8");

    resetGraphifyTopicWorkspace(paths);

    assert.equal(fs.existsSync(path.join(paths.rawRoot, "stale.md")), false);
    assert.equal(fs.existsSync(path.join(paths.wikiRoot, "stale.md")), false);
    assert.equal(fs.existsSync(path.join(paths.graphifyOutRoot, "graph.json")), false);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("graphify refresh request enables execute and wiki bootstrap by default", () => {
  const request = buildGraphifyRefreshRequest("LLM Knowledge Bases");
  assert.deepEqual(request, {
    topic: "LLM Knowledge Bases",
    execute: true,
    buildWiki: true,
    includeArtifacts: false,
    buildSvg: false,
    noViz: false,
    syncVault: true
  });
});

run("graphify refresh runner calls the injected topic executor in-process", () => {
  const calls = [];
  const result = runGraphifyTopicRefresh(
    {
      projectRoot: "C:\\repo\\obsidian-kb-local"
    },
    "Topic Alpha",
    {
      runner(config, request) {
        calls.push({ config, request });
        return { ok: true };
      }
    }
  );

  assert.equal(result.ok, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].config.projectRoot, "C:\\repo\\obsidian-kb-local");
  assert.deepEqual(calls[0].request, {
    topic: "Topic Alpha",
    execute: true,
    buildWiki: true,
    includeArtifacts: false,
    buildSvg: false,
    noViz: false,
    syncVault: true
  });
});

run("refresh wiki views writes machine-maintained dashboard, index and log notes", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-wiki-views-run-tests-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };

    const rawPath = path.join(
      config.vaultPath,
      config.machineRoot,
      "10-raw",
      "books",
      "Money-Supply.md"
    );
    const conceptPath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "concepts",
      "Money-Supply.md"
    );
    const sourcePath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "sources",
      "Money-Supply-Source.md"
    );
    const seedsOnlyReferenceMapPath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "sources",
      "How-Finance-Works-reference-map.md"
    );
    const anthologyReferenceMapPath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "sources",
      "Finance-Trilogy-reference-map.md"
    );
    const mixedCitationReferenceMapPath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "sources",
      "Central-Bank-Bibliography-reference-map.md"
    );
    const logDirectory = path.join(tempRoot, "logs");

    fs.mkdirSync(path.dirname(rawPath), { recursive: true });
    fs.mkdirSync(path.dirname(conceptPath), { recursive: true });
    fs.mkdirSync(path.dirname(sourcePath), { recursive: true });
    fs.mkdirSync(logDirectory, { recursive: true });

    fs.writeFileSync(
      rawPath,
      `${generateFrontmatter("raw", {
        source_type: "epub",
        topic: "Money Supply",
        source_url: "file:///D:/books/money-supply.epub",
        captured_at: "2026-04-04T09:00:00+08:00",
        kb_date: "2026-04-04",
        status: "compiled"
      })}

# Money Supply

Raw source content.
`,
      "utf8"
    );

    fs.writeFileSync(
      conceptPath,
      buildWikiFixture({
        wiki_kind: "concept",
        topic: "Money Supply",
        compiled_from: ["08-ai-kb/10-raw/books/Money-Supply.md"],
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04",
        kb_source_count: 1,
        dedup_key: "money supply::concept::title:money-supply",
        title: "Money Supply",
        body: "## Summary\n\nMoney supply matters."
      }),
      "utf8"
    );

    fs.writeFileSync(
      sourcePath,
      buildWikiFixture({
        wiki_kind: "source",
        topic: "Money Supply",
        compiled_from: ["08-ai-kb/10-raw/books/Money-Supply.md"],
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04",
        kb_source_count: 1,
        dedup_key: "money supply::source::file:///d:/books/money-supply.epub",
        title: "Money Supply Source",
        body: "## Summary\n\nBook digest."
      }),
      "utf8"
    );

    fs.writeFileSync(
      seedsOnlyReferenceMapPath,
      buildWikiFixture({
        wiki_kind: "source",
        topic: "How Finance Works Reference Map",
        compiled_from: ["08-ai-kb/10-raw/books/How-Finance-Works.md"],
        compiled_at: "2026-04-05T08:10:00+08:00",
        kb_date: "2026-04-05",
        kb_source_count: 1,
        dedup_key: "reference-map::how-finance-works",
        title: "How Finance Works Reference Map",
        body: `- Source raw note: [[08-ai-kb/10-raw/books/How-Finance-Works|How Finance Works]]
- Extracted reference entries: 11
- Reference sections: 5
- Strict book titles: 0
- Search-ready book titles: 0
- Recommended titles: 0

## Search Seeds

- Gems from Warren Buffett and Wisdom from 34 Years of Letters to Shareholders

## By Section

### Notes > Chapter 6

- **Gems from Warren Buffett and Wisdom from 34 Years of Letters to Shareholders**: Mark Gavagan, *Gems from Warren Buffett and Wisdom from 34 Years of Letters to Shareholders*. Mendham, NJ: Cole House LLC, 2014.`
      }),
      "utf8"
    );

    fs.writeFileSync(
      anthologyReferenceMapPath,
      buildWikiFixture({
        wiki_kind: "source",
        topic: "Finance Trilogy Reference Map",
        compiled_from: ["08-ai-kb/10-raw/books/Finance-Trilogy.md"],
        compiled_at: "2026-04-05T08:15:00+08:00",
        kb_date: "2026-04-05",
        kb_source_count: 1,
        dedup_key: "reference-map::finance-trilogy",
        title: "Finance Trilogy Reference Map",
        body: `- Source raw note: [[08-ai-kb/10-raw/books/Finance-Trilogy|Finance Trilogy]]
- Extracted reference entries: 0
- Reference sections: 0
- Strict book titles: 0
- Search-ready book titles: 0
- Recommended titles: 0`
      }),
      "utf8"
    );

    fs.writeFileSync(
      mixedCitationReferenceMapPath,
      buildWikiFixture({
        wiki_kind: "source",
        topic: "Central Bank Bibliography Reference Map",
        compiled_from: ["08-ai-kb/10-raw/books/Central-Bank-Bibliography.md"],
        compiled_at: "2026-04-05T08:20:00+08:00",
        kb_date: "2026-04-05",
        kb_source_count: 1,
        dedup_key: "reference-map::central-bank-bibliography",
        title: "Central Bank Bibliography Reference Map",
        body: `- Source raw note: [[08-ai-kb/10-raw/books/Central-Bank-Bibliography|Central Bank Bibliography]]
- Extracted reference entries: 120
- Reference sections: 1
- Strict book titles: 20
- Search-ready book titles: 18
- Recommended titles: 25

## By Section

### BIBLIOGRAPHY

- Monetary Policy and Uncertainty: Adapting to a Changing Economy`
      }),
      "utf8"
    );

    fs.mkdirSync(
      path.join(config.vaultPath, config.machineRoot, "10-raw", "manual"),
      { recursive: true }
    );
    fs.mkdirSync(
      path.join(config.vaultPath, config.machineRoot, "20-wiki", "concepts"),
      { recursive: true }
    );

    fs.writeFileSync(
      path.join(config.vaultPath, config.machineRoot, "10-raw", "manual", "Codex-Thread-Note.md"),
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "Codex thread capture",
        source_url: "codex://threads/thread-a",
        captured_at: "2026-04-05T08:45:00+08:00",
        kb_date: "2026-04-05",
        status: "compiled"
      })}

# Codex Thread Note

## Thread Source

- thread_uri: codex://threads/thread-a
`,
      "utf8"
    );

    fs.writeFileSync(
      path.join(config.vaultPath, config.machineRoot, "20-wiki", "concepts", "Codex-Thread-Concept.md"),
      buildWikiFixture({
        wiki_kind: "concept",
        topic: "Codex thread capture",
        compiled_from: ["08-ai-kb/10-raw/manual/Codex-Thread-Note.md"],
        compiled_at: "2026-04-05T08:50:00+08:00",
        kb_date: "2026-04-05",
        kb_source_count: 1,
        dedup_key: "codex thread capture::concept::codex://threads/thread-a",
        title: "Codex Thread Concept",
        body: "## Summary\n\nThread-derived concept."
      }),
      "utf8"
    );

    fs.writeFileSync(
      path.join(logDirectory, "compile-2026-04-05.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-05T08:00:00+08:00",
        action: "create",
        path: "08-ai-kb/20-wiki/concepts/Money-Supply.md",
        raw_path: "08-ai-kb/10-raw/books/Money-Supply.md"
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "compile-errors-2026-04-05.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-05T08:30:00+08:00",
        raw_path: "08-ai-kb/10-raw/books/Missing.md",
        model: "gpt-5.4",
        error: "gateway timeout"
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "verify-codex-thread-capture-2026-04-05.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-05T08:40:00+08:00",
        total: 2,
        captured: 1,
        missing: 1,
        raw_match_count: 1,
        wiki_match_count: 1,
        thread_uris: ["codex://threads/thread-a", "codex://threads/thread-b"],
        missing_thread_uris: ["codex://threads/thread-b"]
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "capture-codex-thread-2026-04-05.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-05T08:35:00+08:00",
        action: "capture-codex-thread",
        thread_uri: "codex://threads/thread-a",
        topic: "Codex thread capture",
        title: "Codex Thread Note",
        raw_note_path: "08-ai-kb/10-raw/manual/Codex-Thread-Note.md",
        raw_status: "compiled"
      })}\n`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(logDirectory, "reconcile-codex-thread-capture-2026-04-05.jsonl"),
      `${JSON.stringify({
        timestamp: "2026-04-05T08:55:00+08:00",
        total: 2,
        captured: 1,
        missing: 1,
        body_file_count: 1,
        output_dir: "C:/repo/obsidian-kb-local/.tmp-codex-thread-reconcile",
        report_path: "C:/repo/obsidian-kb-local/.tmp-codex-thread-reconcile/verification-report.json",
        manifest_path: "C:/repo/obsidian-kb-local/.tmp-codex-thread-reconcile/missing-manifest.json",
        missing_thread_uris: ["codex://threads/thread-b"]
      })}\n`,
      "utf8"
    );

    const results = refreshWikiViews(config, {
      allowFilesystemFallback: true,
      preferCli: false,
      timestamp: "2026-04-05T09:00:00+08:00"
    });

    assert.equal(results.length, 13);

    const dashboardContent = fs.readFileSync(
      path.join(config.vaultPath, getDashboardPath(config.machineRoot)),
      "utf8"
    );

    const indexContent = fs.readFileSync(
      path.join(config.vaultPath, config.machineRoot, "20-wiki", "_index.md"),
      "utf8"
    );
    const logContent = fs.readFileSync(
      path.join(config.vaultPath, config.machineRoot, "20-wiki", "_log.md"),
      "utf8"
    );
    const auditContent = fs.readFileSync(
      path.join(config.vaultPath, getReferenceMapAuditPath(config.machineRoot)),
      "utf8"
    );
    const graphTopicStatusContent = fs.readFileSync(
      path.join(config.vaultPath, getGraphTopicStatusPath(config.machineRoot)),
      "utf8"
    );
    const codexThreadStatusContent = fs.readFileSync(
      path.join(config.vaultPath, getCodexThreadCaptureStatusPath(config.machineRoot)),
      "utf8"
    );
    const codexRecoveryQueueContent = fs.readFileSync(
      path.join(config.vaultPath, getCodexThreadRecoveryQueuePath(config.machineRoot)),
      "utf8"
    );
    const codexAuditLogContent = fs.readFileSync(
      path.join(config.vaultPath, getCodexThreadAuditLogPath(config.machineRoot)),
      "utf8"
    );

    assert.match(dashboardContent, /## Quick Links/);
    assert.match(dashboardContent, /## Trading Fast Lane/);
    assert.match(dashboardContent, /## Political Economy Fast Lane/);
    assert.match(dashboardContent, /## Maintenance Commands/);
    assert.match(dashboardContent, /refresh-trading-suite/);
    assert.match(dashboardContent, /Trading Card Stack/);
    assert.match(dashboardContent, /Political Economy Sources/);
    assert.match(dashboardContent, /Codex Thread Capture Status/);
    assert.match(dashboardContent, /Recent Reference Cases/);
    assert.match(dashboardContent, /Political Economy Sources/);
    assert.match(dashboardContent, /Trading Card Stack/);
    assert.match(dashboardContent, /Recent Mentor Sessions/);
    assert.match(dashboardContent, /Recent Reference Cases/);
    assert.match(dashboardContent, /Trading Psychology Mentor Hub/);
    assert.match(dashboardContent, /Graph Topic Status/);
    assert.match(dashboardContent, /Codex Thread Capture Status/);
    assert.match(dashboardContent, /Codex Thread Recovery Queue/);
    assert.match(dashboardContent, /Codex Thread Audit Log/);
    assert.match(indexContent, /Wiki Index/);
    assert.match(indexContent, /Raw notes: 2/);
    assert.match(indexContent, /Wiki notes: 6/);
    assert.match(indexContent, /Money Supply/);
    assert.match(indexContent, /Reference Map Audit/);
    assert.match(logContent, /Recent Successful Compiles/);
    assert.match(logContent, /create x1/);
    assert.match(logContent, /gateway timeout/);
    assert.match(auditContent, /Reference maps scanned: 3/);
    assert.match(auditContent, /Zero-entry maps: 1/);
    assert.match(auditContent, /Seeds-only maps: 1/);
    assert.match(auditContent, /Anthology candidates: 1/);
    assert.match(auditContent, /Mixed-citation pressure maps: 1/);
    assert.match(auditContent, /Backmatter-recovered maps: 2/);
    assert.match(auditContent, /How Finance Works/);
    assert.match(auditContent, /Finance Trilogy/);
    assert.match(graphTopicStatusContent, /Graph Topic Status/);
    assert.match(codexThreadStatusContent, /Codex Thread Capture Status/);
    assert.match(codexThreadStatusContent, /tracked thread URIs: 1/);
    assert.match(codexThreadStatusContent, /Codex-Thread-Note/);
    assert.match(codexThreadStatusContent, /thread-a/);
    assert.match(codexThreadStatusContent, /Codex-Thread-Concept/);
    assert.match(codexThreadStatusContent, /Recent Verify Runs/);
    assert.match(codexThreadStatusContent, /Recent Reconcile Runs/);
    assert.match(codexThreadStatusContent, /Latest Missing Threads/);
    assert.match(codexThreadStatusContent, /Latest Recovery Package/);
    assert.match(codexThreadStatusContent, /2026-04-05T08:40:00\+08:00/);
    assert.match(codexThreadStatusContent, /2026-04-05T08:55:00\+08:00/);
    assert.match(codexThreadStatusContent, /codex:\/\/threads\/thread-b/);
    assert.match(codexThreadStatusContent, /missing-manifest\.json/);
    assert.match(codexThreadStatusContent, /capture-codex-thread-batch\.mjs --manifest/);
    assert.match(codexRecoveryQueueContent, /Codex Thread Recovery Queue/);
    assert.match(codexRecoveryQueueContent, /Pending Recovery Runs/);
    assert.match(codexRecoveryQueueContent, /codex:\/\/threads\/thread-b/);
    assert.match(codexAuditLogContent, /Codex Thread Audit Log/);
    assert.match(codexAuditLogContent, /Recent Events/);
    assert.match(codexAuditLogContent, /capture/);
    assert.match(codexAuditLogContent, /verify/);
    assert.match(codexAuditLogContent, /reconcile/);
    assert.match(codexAuditLogContent, /2026-04-05T08:35:00\+08:00/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("refresh wiki views disables CLI after the first fallback attempt", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-wiki-views-cli-fallback-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };
    const notes = [
      {
        path: "08-ai-kb/30-views/00-System/First.md",
        content: "# First\n"
      },
      {
        path: "08-ai-kb/30-views/00-System/Second.md",
        content: "# Second\n"
      },
      {
        path: "08-ai-kb/30-views/00-System/Third.md",
        content: "# Third\n"
      }
    ];
    const preferCliCalls = [];

    const results = refreshWikiViews(config, {
      allowFilesystemFallback: true,
      preferCli: true,
      notes,
      writeNote(_config, note, options) {
        preferCliCalls.push({
          path: note.path,
          preferCli: options.preferCli
        });

        if (note.path.endsWith("First.md")) {
          return {
            mode: "filesystem-fallback",
            path: note.path,
            cliAttempted: true,
            cliErrorCode: "OBSIDIAN_CLI_TIMEOUT",
            cliErrorMessage: "Obsidian CLI timed out"
          };
        }

        return {
          mode: "filesystem-fallback",
          path: note.path,
          cliAttempted: false,
          cliErrorCode: null,
          cliErrorMessage: null
        };
      }
    });

    assert.equal(results.length, 3);
    assert.deepEqual(
      preferCliCalls.map((entry) => entry.preferCli),
      [true, false, false]
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("wiki query selector prioritizes title and topic matches", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply.md",
      title: "Money Supply",
      content: `# Money Supply

Changes in money supply affect credit conditions and liquidity.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Money Supply",
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/sources/Inflation-Source.md",
      title: "Inflation Source",
      content: `# Inflation Source

Inflation remained elevated.
`,
      frontmatter: {
        wiki_kind: "source",
        topic: "Inflation",
        compiled_at: "2026-04-03T12:00:00+08:00",
        kb_date: "2026-04-03"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply effects", {
    limit: 1
  });

  assert.equal(selected.length, 1);
  assert.equal(selected[0].note.title, "Money Supply");
  assert.match(selected[0].excerpt, /money supply/i);
  assert.equal(selected[0].retrieval.mode, "direct");
  assert.ok(selected[0].retrieval.directScore > 0);
});

run("wiki query selector expands linked support notes through graph retrieval", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply.md",
      title: "Money Supply",
      content: `# Money Supply

Money supply affects credit conditions and liquidity.

## Related

- [[08-ai-kb/20-wiki/sources/Liquidity-Plumbing|Liquidity Plumbing]]
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Money Supply",
        compiled_from: ["08-ai-kb/10-raw/books/Money-Supply.md"],
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/sources/Market-Plumbing.md",
      title: "Market Plumbing",
      content: `# Market Plumbing

Collateral plumbing and backstop mechanics shape market transmission.
`,
      frontmatter: {
        wiki_kind: "source",
        topic: "Market Plumbing",
        compiled_from: ["08-ai-kb/10-raw/books/Money-Supply.md"],
        compiled_at: "2026-04-04T11:30:00+08:00",
        kb_date: "2026-04-04"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Inflation.md",
      title: "Inflation",
      content: `# Inflation

Inflation remained elevated.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Inflation",
        compiled_at: "2026-04-03T12:00:00+08:00",
        kb_date: "2026-04-03"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply effects", {
    limit: 2
  });

  assert.equal(selected.length, 2);
  assert.equal(selected[0].note.title, "Money Supply");
  assert.equal(selected[1].note.title, "Market Plumbing");
  assert.equal(selected[1].retrieval.mode, "graph");
  assert.ok(selected[1].retrieval.graphScore > 0);
  assert.match(selected[1].retrieval.signals.join(" "), /(linked|shared-source)/);
});

run("wiki query selector prefers coherent multi-term matches over scattered hits", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/sources/How-to-Make-Money.md",
      title: "How to Make Money",
      content: `# How to Make Money

Supply and demand matter in chart reading.
`,
      frontmatter: {
        wiki_kind: "source",
        topic: "Trading Rules",
        compiled_at: "2026-04-04T12:00:00+08:00",
        kb_date: "2026-04-04"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply.md",
      title: "Liquidity Note",
      content: `# Liquidity Note

Money supply influences credit creation and liquidity conditions.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Monetary Economics",
        compiled_at: "2026-04-04T12:30:00+08:00",
        kb_date: "2026-04-04"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply", {
    limit: 2
  });

  assert.equal(selected.length, 2);
  assert.equal(selected[0].note.title, "Liquidity Note");
  assert.ok(selected[0].score > selected[1].score);
});

run("wiki query selector diversifies results across topics and source clusters", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/sources/Cluster-A-Source.md",
      title: "Cluster A Source",
      content: `# Cluster A Source

Money supply appears in a broad survey note.

## Related

- [[08-ai-kb/20-wiki/concepts/Cluster-A-Concept|Cluster A Concept]]
`,
      frontmatter: {
        wiki_kind: "source",
        topic: "Cluster A",
        compiled_from: ["08-ai-kb/10-raw/books/cluster-a.md"],
        compiled_at: "2026-04-05T08:00:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Cluster-A-Concept.md",
      title: "Cluster A Concept",
      content: `# Cluster A Concept

Money supply and liquidity conditions are summarized here.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Cluster A",
        compiled_from: ["08-ai-kb/10-raw/books/cluster-a.md"],
        compiled_at: "2026-04-05T07:30:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Cluster-B-Concept.md",
      title: "Cluster B Concept",
      content: `# Cluster B Concept

Money supply links to central bank liquidity and dealer-of-last-resort mechanics.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Cluster B",
        compiled_from: ["08-ai-kb/10-raw/books/cluster-b.md"],
        compiled_at: "2026-04-05T07:00:00+08:00",
        kb_date: "2026-04-05"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply", {
    limit: 2
  });

  assert.equal(selected.length, 2);
  assert.notEqual(selected[0].note.frontmatter.topic, selected[1].note.frontmatter.topic);
});

run("wiki query selector keeps graph-only support from outranking stronger direct multi-term hits", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/sources/Direct-Match.md",
      title: "Direct Match",
      content: `# Direct Match

Money supply drives liquidity in this note.
`,
      frontmatter: {
        wiki_kind: "source",
        topic: "Monetary Policy",
        compiled_from: ["08-ai-kb/10-raw/books/direct.md"],
        compiled_at: "2026-04-05T08:00:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Support-Node.md",
      title: "Support Node",
      content: `# Support Node

Money matters for this concept.

## Related

- [[08-ai-kb/20-wiki/sources/Direct-Match|Direct Match]]
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Monetary Policy",
        compiled_from: ["08-ai-kb/10-raw/books/direct.md"],
        compiled_at: "2026-04-05T07:30:00+08:00",
        kb_date: "2026-04-05"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply", {
    limit: 2
  });

  assert.equal(selected.length, 2);
  assert.equal(selected[0].note.title, "Direct Match");
  assert.ok(selected[0].score > selected[1].score);
});

run("wiki query selector uses intent expansion to recall monetary plumbing notes", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/sources/How-to-Make-Money.md",
      title: "How to Make Money",
      content: `# How to Make Money

Supply and demand help traders build routines.
`,
      frontmatter: {
        wiki_kind: "source",
        topic: "Trading Rules",
        compiled_at: "2026-04-05T09:00:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Quantitative-Easing.md",
      title: "Quantitative Easing",
      content: `# Quantitative Easing

Central bank balance-sheet expansion injects liquidity into the financial system.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Monetary Policy",
        compiled_at: "2026-04-05T09:10:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Dealer-of-Last-Resort.md",
      title: "Dealer of Last Resort",
      content: `# Dealer of Last Resort

The dealer-of-last-resort framework explains Fed liquidity backstops in market stress.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Central Bank Plumbing",
        compiled_at: "2026-04-05T09:05:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Money-View.md",
      title: "Money View",
      content: `# Money View

The money view links monetary hierarchy, dealer balance sheets, and credit creation.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Monetary Theory",
        compiled_at: "2026-04-05T09:20:00+08:00",
        kb_date: "2026-04-05"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply", {
    limit: 4
  });

  const selectedTitles = selected.map((entry) => entry.note.title);
  assert.ok(selectedTitles.includes("Quantitative Easing"));
  assert.ok(selectedTitles.includes("Dealer of Last Resort"));

  const qeEntry = selected.find((entry) => entry.note.title === "Quantitative Easing");
  const dealerEntry = selected.find((entry) => entry.note.title === "Dealer of Last Resort");
  assert.ok(qeEntry);
  assert.ok(dealerEntry);
  assert.equal(qeEntry.retrieval.intentLabel, "monetary-liquidity");
  assert.equal(dealerEntry.retrieval.directBasis, "intent-expansion");
  assert.ok(qeEntry.retrieval.expansionScore > 0);
  assert.ok(dealerEntry.retrieval.expansionMatches.includes("dealer of last resort"));
});

run("wiki query selector keeps direct phrase hits ahead of intent expansion hits", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply-Primer.md",
      title: "Money Supply Primer",
      content: `# Money Supply Primer

Money supply is the stock of money available in the economy and shapes liquidity conditions.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Money Supply",
        compiled_at: "2026-04-05T09:30:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Quantitative-Easing.md",
      title: "Quantitative Easing",
      content: `# Quantitative Easing

Central bank liquidity programs expand credit creation and reserves.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Monetary Policy",
        compiled_at: "2026-04-05T09:40:00+08:00",
        kb_date: "2026-04-05"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply", {
    limit: 2
  });

  assert.equal(selected.length, 2);
  assert.equal(selected[0].note.title, "Money Supply Primer");
  assert.ok(selected[0].retrieval.directScore > selected[1].retrieval.directScore);
  assert.ok(selected[1].retrieval.expansionScore > 0);
});

run("wiki query selector ignores english stopwords in question-shaped queries", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply-Primer.md",
      title: "Money Supply Primer",
      content: `# Money Supply Primer

Money supply is the stock of money available in the economy.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Monetary Economics",
        compiled_at: "2026-04-05T10:00:00+08:00",
        kb_date: "2026-04-05"
      }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/Shadow-Banking.md",
      title: "Shadow Banking",
      content: `# Shadow Banking

Shadow banking is a system that is important in modern finance.
`,
      frontmatter: {
        wiki_kind: "concept",
        topic: "Financial Stability",
        compiled_at: "2026-04-05T10:05:00+08:00",
        kb_date: "2026-04-05"
      }
    }
  ];

  const selected = selectRelevantWikiNotes(notes, "what is money supply", {
    limit: 2
  });

  assert.equal(selected.length, 1);
  assert.equal(selected[0].note.title, "Money Supply Primer");
  assert.ok(!selected[0].retrieval.matchedTerms.includes("is"));
});

run("wiki query prompt injects selected note context", () => {
  const prompt = buildWikiQueryPrompt("Q={{QUERY}}\nT={{TOPIC}}\nN={{NOTE_CONTEXT}}", {
    query: "What is money supply?",
    topic: "Money Supply",
    selectedNotes: [
      {
        score: 42,
        note: {
          relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply.md",
          title: "Money Supply",
          frontmatter: {
            wiki_kind: "concept",
            topic: "Money Supply",
            kb_date: "2026-04-04"
          }
        },
        excerpt: "Money supply affects liquidity."
      }
    ]
  });

  assert.match(prompt, /Q=What is money supply\?/);
  assert.match(prompt, /T=Money Supply/);
  assert.match(prompt, /money supply affects liquidity\./i);
  assert.match(prompt, /score: 42/);
});

run("wiki query prompt includes retrieval summary when available", () => {
  const prompt = buildWikiQueryPrompt("N={{NOTE_CONTEXT}}", {
    query: "What is money supply?",
    topic: "Money Supply",
    selectedNotes: [
      {
        score: 64.5,
        retrieval: {
          mode: "direct+graph",
          directScore: 48,
          graphScore: 12,
          rrfScore: 4.5,
          matchedTerms: ["money", "supply"],
          signals: ["title:phrase", "linked:Liquidity Plumbing"]
        },
        note: {
          relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply.md",
          title: "Money Supply",
          frontmatter: {
            wiki_kind: "concept",
            topic: "Money Supply",
            kb_date: "2026-04-04"
          }
        },
        excerpt: "Money supply affects liquidity."
      }
    ]
  });

  assert.match(prompt, /retrieval: direct\+graph/);
  assert.match(prompt, /terms=money, supply/);
  assert.match(prompt, /signals=title:phrase; linked:Liquidity Plumbing/);
});

run("wiki query synthesis builder emits valid wiki frontmatter", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-wiki-query-run-tests-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };

    const result = buildQuerySynthesisNote(config, {
      query: "What is money supply?",
      topic: "Money Supply",
      answer: "## Answer\n\nMoney supply is the stock of money available in the economy.",
      selectedNotes: [
        {
          score: 37,
          note: {
            relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply.md",
            title: "Money Supply",
            frontmatter: {
              wiki_kind: "concept",
              topic: "Money Supply",
              kb_date: "2026-04-04"
            }
          }
        }
      ],
      timestamp: "2026-04-05T09:00:00+08:00"
    });

    const frontmatter = parseFrontmatter(result.content);
    assert.ok(frontmatter);
    assert.doesNotThrow(() => validateWikiFrontmatter(frontmatter));
    assert.equal(frontmatter.topic, "Money Supply");
    assert.deepEqual(frontmatter.compiled_from, ["08-ai-kb/20-wiki/concepts/Money-Supply.md"]);
    assert.match(result.path, /20-wiki\/syntheses\/Q&A-Money-Supply/i);
    assert.match(result.content, /## Query/);
    assert.match(
      result.content,
      /\[\[08-ai-kb\/20-wiki\/concepts\/Money-Supply\|Money Supply\]\]/
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("query wiki command falls back to graphify workspace notes for scoped topics", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-query-wiki-graphify-"));

  try {
    const config = {
      vaultPath: path.join(tempRoot, "vault"),
      vaultName: "Test Vault",
      machineRoot: "08-ai-kb",
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };

    const vaultNotePath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "concepts",
      "Workflow-Adoption.md"
    );
    const sidecarNotePath = path.join(
      tempRoot,
      "graphify-sidecar",
      "AI-knowledge-workflows",
      "input",
      "wiki",
      "concept",
      "Workflow-Adoption.md"
    );
    const manifestPath = path.join(
      tempRoot,
      "graphify-sidecar",
      "AI-knowledge-workflows",
      "manifest.json"
    );

    fs.mkdirSync(path.dirname(vaultNotePath), { recursive: true });
    fs.mkdirSync(path.dirname(sidecarNotePath), { recursive: true });

    const content = buildWikiFixture({
      wiki_kind: "concept",
      topic: "Karpathy thread follow-up",
      compiled_from: ["08-ai-kb/10-raw/articles/Karpathy-thread.md"],
      compiled_at: "2026-04-08T09:30:00+08:00",
      kb_date: "2026-04-08",
      kb_source_count: 1,
      dedup_key: "karpathy-thread-follow-up::concept::title:workflow-adoption",
      title: "Workflow Adoption",
      body: "## Summary\n\nWorkflow adoption depends on entrypoints, permissions, and repeatable operator flow."
    });

    fs.writeFileSync(vaultNotePath, content, "utf8");
    fs.writeFileSync(sidecarNotePath, content, "utf8");
    fs.writeFileSync(
      manifestPath,
      JSON.stringify(
        {
          topic: "AI knowledge workflows",
          slug: "AI-knowledge-workflows",
          wikiNotes: [
            {
              destination: sidecarNotePath,
              relativePath: "08-ai-kb/20-wiki/concepts/Workflow-Adoption.md",
              wikiKind: "concept"
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );

    const logs = [];
    const result = await executeQueryWikiCommand(
      {
        query: "workflow adoption permissions",
        topic: "AI knowledge workflows",
        dryRun: true
      },
      {
        config,
        templateContent: "Q={{QUERY}}\nT={{TOPIC}}\n{{NOTE_CONTEXT}}",
        writer: {
          log(message = "") {
            logs.push(String(message));
          }
        }
      }
    );

    assert.equal(result.executed, false);
    assert.equal(result.selectedNotes.length, 1);
    assert.equal(result.selectedNotes[0].note.title, "Workflow-Adoption");
    assert.match(result.prompt, /workflow adoption permissions/i);
    assert.ok(
      logs.some((line) => /falling back to graphify workspace AI-knowledge-workflows/i.test(line))
    );
    assert.ok(
      logs.some((line) => /Topic scope resolution: graphify-sidecar:AI-knowledge-workflows/.test(line))
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("query wiki parser keeps explicit topic and write-synthesis flags", () => {
  const parsed = parseQueryWikiCliArgs([
    "--query",
    "workflow adoption permissions",
    "--topic",
    "AI knowledge workflows",
    "--execute",
    "--write-synthesis",
    "--timeout-ms",
    "240000"
  ]);

  assert.equal(parsed.query, "workflow adoption permissions");
  assert.equal(parsed.topic, "AI knowledge workflows");
  assert.equal(parsed.execute, true);
  assert.equal(parsed.writeSynthesis, true);
  assert.equal(parsed.timeoutMs, 240000);
});

run("query wiki cli error reporter prints usage for usage errors", () => {
  const lines = [];
  const error = new Error("Missing required --query argument.");
  error.code = "USAGE";

  reportCliError(error, (line) => {
    lines.push(String(line));
  });

  assert.equal(lines.length, 3);
  assert.match(lines[0], /^Usage: node scripts\/query-wiki\.mjs --query <text>/);
  assert.equal(lines[1], "");
  assert.equal(lines[2], "Missing required --query argument.");
});

run("query wiki cli error reporter skips usage for runtime errors", () => {
  const lines = [];

  reportCliError(
    new Error(
      "Responses API completed at https://gateway.example.test/v1/responses but returned no textual output"
    ),
    (line) => {
      lines.push(String(line));
    }
  );

  assert.deepEqual(lines, [
    "Responses API completed at https://gateway.example.test/v1/responses but returned no textual output"
  ]);
});

run("query wiki batch parser ignores comments and blank lines", () => {
  const parsed = parseQueriesFromText(`
# comment
money supply

   # another comment
trading psychology
investment portfolio
`);

  assert.deepEqual(parsed, ["money supply", "trading psychology", "investment portfolio"]);
});

run("query wiki batch parser defaults to continue-on-error unless fail-fast is set", () => {
  const defaultParsed = parseQueryWikiBatchCliArgs(["--queries-file", "queries.txt"]);
  assert.equal(defaultParsed.continueOnError, true);

  const continueParsed = parseQueryWikiBatchCliArgs([
    "--queries-file",
    "queries.txt",
    "--continue-on-error"
  ]);
  assert.equal(continueParsed.continueOnError, true);

  const failFastParsed = parseQueryWikiBatchCliArgs([
    "--queries-file",
    "queries.txt",
    "--fail-fast"
  ]);
  assert.equal(failFastParsed.continueOnError, false);
});

run("query wiki batch parser rejects conflicting error handling flags", () => {
  assert.throws(
    () =>
      parseQueryWikiBatchCliArgs([
        "--queries-file",
        "queries.txt",
        "--continue-on-error",
        "--fail-fast"
      ]),
    /Choose either --continue-on-error or --fail-fast, not both\./
  );
});

run("import x-index parser recognizes compile and link flags", () => {
  const parsed = parseImportXIndexCliArgs([
    "--input",
    "..\\.tmp\\linqingv-result.json",
    "--post-id",
    "2041135310852235487",
    "--post-id",
    "2041015554740543812",
    "--topic",
    "涓浗姹借溅鍑烘捣閾撅細姣斾簹杩€佷笂姹姐€佺鑰€鐜荤拑",
    "--compile",
    "--skip-links",
    "--timeout-ms",
    "300000"
  ]);

  assert.match(parsed.inputPath, /linqingv-result\.json$/);
  assert.deepEqual(parsed.postIds, ["2041135310852235487", "2041015554740543812"]);
  assert.equal(parsed.topic, "涓浗姹借溅鍑烘捣閾撅細姣斾簹杩€佷笂姹姐€佺鑰€鐜荤拑");
  assert.equal(parsed.compile, true);
  assert.equal(parsed.healthCheck, true);
  assert.equal(parsed.rebuildTopic, false);
  assert.equal(parsed.skipLinks, true);
  assert.equal(parsed.timeoutMs, 300000);
});

run("import x-index parser rejects conflicting health-check flags", () => {
  assert.throws(
    () =>
      parseImportXIndexCliArgs([
        "--input",
        "result.json",
        "--health-check",
        "--skip-health-check"
      ]),
    /Choose either --health-check or --skip-health-check, not both\./
  );
});

run("import x-index parser recognizes rebuild-topic flag", () => {
  const parsed = parseImportXIndexCliArgs([
    "--input",
    "result.json",
    "--topic",
    "China Auto Export",
    "--compile",
    "--rebuild-topic"
  ]);

  assert.equal(parsed.compile, true);
  assert.equal(parsed.rebuildTopic, true);
  assert.equal(parsed.healthCheck, true);
});

run("import x-index parser recognizes smart-closeout flag", () => {
  const parsed = parseImportXIndexCliArgs([
    "--input",
    "result.json",
    "--topic",
    "China Auto Export",
    "--compile",
    "--smart-closeout"
  ]);

  assert.equal(parsed.compile, true);
  assert.equal(parsed.smartCloseout, true);
  assert.equal(parsed.rebuildTopic, false);
});

run("decideTopicRebuild triggers only when smart closeout sees stale notes for the topic", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-smart-closeout-"));

  try {
    const { config, rawPath } = createCompileFixture(tempRoot);
    const topic = "LLM Knowledge Bases";
    const wikiRoot = path.join(config.vaultPath, config.machineRoot, "20-wiki");
    fs.mkdirSync(path.join(wikiRoot, "sources"), { recursive: true });

    fs.writeFileSync(
      path.join(wikiRoot, "sources", "Karpathy-Source.md"),
      buildWikiFixture({
        wiki_kind: "source",
        topic,
        compiled_from: [rawPath],
        compiled_at: "2026-04-03T12:00:00+08:00",
        kb_date: "2026-04-03",
        kb_source_count: 1,
        dedup_key: "llm knowledge bases::source::https://example.com/article",
        title: "Karpathy Source",
        body: "## Summary\n\nStale content."
      }),
      "utf8"
    );

    assert.equal(
      decideTopicRebuild({
        config,
        successfulCompiles: 1,
        options: {
          topic,
          smartCloseout: true,
          rebuildTopic: false
        }
      }),
      true
    );

    assert.equal(
      decideTopicRebuild({
        config,
        successfulCompiles: 1,
        options: {
          topic,
          smartCloseout: false,
          rebuildTopic: false
        }
      }),
      false
    );

    assert.equal(
      decideTopicRebuild({
        config,
        successfulCompiles: 1,
        options: {
          topic,
          smartCloseout: false,
          rebuildTopic: true
        }
      }),
      true
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("query wiki batch summarizes multi-query runs and finalizes links/views once", async () => {
  const calls = [];
  let rebuilt = 0;
  let refreshed = 0;
  const writer = {
    log() {},
    error() {}
  };

  const summary = await runQueryWikiBatch(
    {
      queries: ["money supply", "bad query", "portfolio diversification"],
      execute: true,
      writeSynthesis: true,
      dryRun: false,
      skipLinks: false,
      continueOnError: true,
      limit: 6
    },
    {
      writer,
      config: {
        projectRoot: process.cwd(),
        vaultPath: process.cwd(),
        machineRoot: "08-ai-kb",
        obsidian: {
          cliCandidates: [],
          exeCandidates: []
        }
      },
      templateContent: "# template",
      provider: {
        providerName: "custom",
        model: "gpt-5.4",
        baseUrl: "https://gateway.example.test",
        wireApi: "responses",
        configPath: "C:/tmp/config.toml"
      },
      runSingleQuery: async (command) => {
        calls.push(command);
        if (command.query === "bad query") {
          throw new Error("simulated failure");
        }
        return {
          query: command.query,
          writeResult: {
            path: `08-ai-kb/20-wiki/syntheses/${sanitizeFilename(command.query)}.md`,
            mode: "cli"
          }
        };
      },
      rebuildLinksFn: () => {
        rebuilt += 1;
        return {
          updated: 4,
          scanned: 20
        };
      },
      refreshViewsFn: () => {
        refreshed += 1;
        return [
          { path: "08-ai-kb/20-wiki/_index.md", mode: "cli" },
          { path: "08-ai-kb/20-wiki/_log.md", mode: "cli" }
        ];
      }
    }
  );

  assert.equal(summary.total, 3);
  assert.equal(summary.completed, 2);
  assert.equal(summary.failed, 1);
  assert.equal(rebuilt, 1);
  assert.equal(refreshed, 1);
  assert.equal(calls.length, 3);
  for (const command of calls) {
    assert.equal(command.skipLinks, true);
    assert.equal(command.skipViews, true);
  }
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

run("epub container parser extracts the rootfile path", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml" />
  </rootfiles>
</container>`;

  assert.equal(parseContainerRootfile(xml), "OEBPS/content.opf");
});

run("opf parser handles mixed manifest markup and dc description fields", () => {
  const xml = `<package>
  <metadata>
    <dc:title>Money &amp; Banking</dc:title>
    <dc:creator>Jane Doe</dc:creator>
    <dc:publisher>Vault Press</dc:publisher>
    <dc:language>en</dc:language>
    <dc:identifier>isbn-123</dc:identifier>
    <dc:description>Central bank basics</dc:description>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml"></item>
    <item id="ch1" href="text/ch1.xhtml" media-type="application/xhtml+xml" />
  </manifest>
  <spine>
    <itemref idref="nav" linear="no"></itemref>
    <itemref idref="ch1" />
  </spine>
</package>`;

  const parsed = parseOpfPackage(xml);
  assert.equal(parsed.metadata.title, "Money & Banking");
  assert.equal(parsed.metadata.creator, "Jane Doe");
  assert.equal(parsed.metadata.description, "Central bank basics");
  assert.equal(parsed.manifest.get("ch1").href, "text/ch1.xhtml");
  assert.deepEqual(parsed.spine, ["ch1"]);
});

run("xhtml converter promotes chapter markers and preserves basic structure", () => {
  const markdown = convertXhtmlToMarkdown(`<html><body>
    <p class="cn">1</p>
    <p class="ct">THE GREAT INFLATION</p>
    <p>First paragraph.</p>
    <blockquote>Quoted line.</blockquote>
    <li>Bullet item</li>
    <p class="h1">绗簩绔?璐у竵</p>
  </body></html>`);

  assert.match(markdown, /^## 1 THE GREAT INFLATION/m);
  assert.match(markdown, /First paragraph\./);
  assert.match(markdown, /^> Quoted line\./m);
  assert.match(markdown, /^- Bullet item/m);
  assert.equal(markdown.includes("Bullet item\n\n## "), true);
});

run("finance book filter ignores related-link pollution in note bodies", () => {
  const note = {
    title: "The Book of Elon",
    frontmatter: {
      topic: "The Book of Elon"
    },
    sourcePath: "D:\\涓嬭浇\\The Book of Elon.epub",
    body: `# The Book of Elon

## Related

- [[How to Make Money in Stocks|How to Make Money in Stocks]]`,
    hasExtractedMarkdown: false
  };

  assert.equal(isFinanceRelatedBookCandidate(note), false);
});

run("finance selector deduplicates repeated books and prefers stronger candidates", () => {
  const notes = [
    {
      title: "Money Origins",
      frontmatter: {
        topic: "Money Origins"
      },
      sourcePath: "D:/books/Money-Origins.epub",
      body: "# Money Origins",
      hasExtractedMarkdown: false
    },
    {
      title: "Money Origins",
      frontmatter: {
        topic: "Money Origins"
      },
      sourcePath: "D:/desktop-books/Money-Origins.epub",
      body: "# Money Origins",
      hasExtractedMarkdown: true
    }
  ];

  const selected = selectFinanceRelatedBookNotes(notes);
  assert.equal(selected.length, 1);
  assert.equal(selected[0].sourcePath, "D:/desktop-books/Money-Origins.epub");
  assert.equal(selected[0].hasExtractedMarkdown, true);
});

run("epub compile digest compresses oversized raw notes while keeping section coverage", () => {
  const rawNote = {
    title: "Long Book",
    frontmatter: {
      topic: "Long Book",
      source_url: "file:///D:/books/long-book.epub"
    },
    content: `${generateFrontmatter("raw", {
      source_type: "epub",
      topic: "Long Book",
      source_url: "file:///D:/books/long-book.epub",
      captured_at: "2026-04-04T10:00:00+08:00",
      kb_date: "2026-04-04",
      status: "queued"
    })}

# Long Book

## Book Metadata

- Title: Long Book
- Author: Test Author

## Table of Contents

- Part One
- Part Two

## Extracted Markdown

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
  assert.match(digest, /### Part One/);
  assert.match(digest, /### Part Two/);
  assert.match(digest, /\[Excerpt truncated\]/);
});

run("epub compile digest skips toc and copyright noise from older raw notes", () => {
  const rawNote = {
    title: "Money Notes",
    frontmatter: {
      topic: "Money Notes",
      source_url: "file:///D:/books/money.epub"
    },
    content: `---
kb_type: raw
source_type: epub
topic: Money Notes
source_url: file:///D:/books/money.epub
captured_at: 2026-04-04T10:00:00+08:00
kb_date: 2026-04-04
status: queued
managed_by: codex
---

# Money Notes

## Extracted Markdown

## Table of Contents

- Preface
- Chapter 1

## Copyright Information

Publisher: Example Press
ISBN: 1234567890

## Chapter 1

${"Monetary policy and liquidity conditions shape markets. ".repeat(120)}

## Chapter 2

${"Trading behavior often diverges from long-term investing discipline. ".repeat(120)}
`
  };

  const digest = buildEpubCompileDigest(rawNote, {
    maxChars: 1800,
    minExcerptChars: 120,
    maxExcerptChars: 220
  });

  assert.doesNotMatch(digest, /### Table of Contents/);
  assert.doesNotMatch(digest, /### Copyright Information/);
  assert.match(digest, /### Chapter 1/);
  assert.match(digest, /### Chapter 2/);
});

run("epub compile prompt variants emit descending fallback digests for very long books", () => {
  const repeatedSection = "0123456789 ".repeat(2500);
  const toc = Array.from({ length: 20 }, (_, index) => `- Part ${index + 1}`).join("\n");
  const extractedMarkdown = Array.from(
    { length: 20 },
    (_, index) => `## Part ${index + 1}\n\n${repeatedSection}`
  ).join("\n\n");
  const rawNote = {
    title: "Massive Book",
    frontmatter: {
      topic: "Massive Book",
      source_url: "file:///D:/books/massive-book.epub"
    },
    content: `# Massive Book

## Book Metadata

- Title: Massive Book

## Table of Contents

${toc}

## Extracted Markdown

${extractedMarkdown}
`
  };

  const variants = buildEpubCompilePromptVariants(rawNote, {
    maxCharsVariants: [12000, 8000, 6000]
  });

  assert.equal(variants.length, 3);
  assert.deepEqual(
    variants.map((variant) => variant.label),
    ["epub-digest-12000", "epub-digest-8000", "epub-digest-6000"]
  );
  assert.ok(variants[0].promptContent.length > variants[1].promptContent.length);
  assert.ok(variants[1].promptContent.length > variants[2].promptContent.length);
});

run("compile prompt injects raw content and topic context", () => {
  const prompt = buildCompilePrompt(
    "RAW={{RAW_CONTENT}}\nTOPIC={{TOPIC}}\nNOTES={{EXISTING_NOTES}}",
    {
      content: "---\nkb_type: raw\n---\n\n# Raw",
      promptContent: "CONDENSED RAW",
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
  assert.match(prompt, /RAW=CONDENSED RAW/);
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
base_url = "https://gateway.example.test"
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
    assert.equal(provider.baseUrl, "https://gateway.example.test");
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

run("codex config accepts chatgpt auth mode without an api key", () => {
  const codexHome = fs.mkdtempSync(path.join(tmpdir(), "obsidian-kb-chatgpt-home-"));

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
      JSON.stringify({
        OPENAI_API_KEY: null,
        auth_mode: "chatgpt",
        tokens: {
          access_token: "access-token"
        }
      }),
      "utf8"
    );

    const provider = loadCodexLlmProvider({
      env: {
        CODEX_HOME: codexHome
      }
    });

    assert.equal(provider.providerName, "openai");
    assert.equal(provider.baseUrl, "https://api.openai.com/v1");
    assert.equal(provider.apiKey, null);
    assert.equal(provider.authMode, "chatgpt");
    assert.equal(provider.canUseChatGptSession, true);
  } finally {
    fs.rmSync(codexHome, { recursive: true, force: true });
  }
});

run("codex provider route detail includes fallback markers for chatgpt auth mode", () => {
  const provider = {
    providerName: "openai",
    model: "gpt-5.4",
    wireApi: "responses",
    baseUrl: "https://api.openai.com/v1",
    authMode: "chatgpt",
    apiKey: null,
    requiresOpenAiAuth: true,
    canUseChatGptSession: true
  };

  const route = describeCodexProviderRoute(provider);
  const detail = formatCodexProviderRouteDetail(provider);

  assert.equal(route.ok, true);
  assert.equal(route.route, "codex-exec-fallback");
  assert.match(detail, /openai \| gpt-5\.4 \| responses \| https:\/\/api\.openai\.com\/v1/);
  assert.match(detail, /route:codex-exec-fallback/);
  assert.match(detail, /auth-mode:chatgpt/);
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
  assert.deepEqual(buildResponseEndpointCandidates("https://gateway.example.test", "responses"), [
    "https://gateway.example.test/responses",
    "https://gateway.example.test/v1/responses"
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

run("responses output extractor explains completed-but-empty payloads", () => {
  assert.throws(
    () =>
      extractResponseOutputText(
        {
          status: "completed",
          output: [],
          usage: {
            output_tokens: 5
          }
        },
        {
          endpoint: "https://gateway.example.test/responses"
        }
      ),
    (error) => {
      assert.equal(error.code, "EMPTY_RESPONSE_TEXT");
      assert.match(error.message, /completed at https:\/\/gateway\.example\.test\/responses/i);
      assert.match(error.message, /output_tokens=5/);
      assert.match(error.message, /Auth appears accepted/i);
      return true;
    }
  );
});

run("responses caller retries /v1 fallback after a 404 and preserves auth header", async () => {
  const calls = [];
  const provider = {
    providerName: "custom",
    model: "gpt-5.4",
    baseUrl: "https://gateway.example.test",
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
  assert.equal(calls[0].url, "https://gateway.example.test/responses");
  assert.equal(calls[1].url, "https://gateway.example.test/v1/responses");
  assert.equal(calls[1].init.headers.authorization, "Bearer sk-test");
  assert.equal(result.endpoint, "https://gateway.example.test/v1/responses");
});

run("responses caller retries fallback endpoint after completed-but-empty response", async () => {
  const calls = [];
  const provider = {
    providerName: "custom",
    model: "gpt-5.4",
    baseUrl: "https://gateway.example.test",
    wireApi: "responses",
    apiKey: "sk-test"
  };

  const result = await callResponsesApi(provider, "Compile this note", {
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      if (calls.length === 1) {
        return {
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({
              status: "completed",
              output: [],
              usage: {
                output_tokens: 5
              }
            })
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
  assert.equal(calls[0].url, "https://gateway.example.test/responses");
  assert.equal(calls[1].url, "https://gateway.example.test/v1/responses");
  assert.equal(calls[1].init.headers.authorization, "Bearer sk-test");
  assert.equal(result.endpoint, "https://gateway.example.test/v1/responses");
});

run("responses caller retries transient 524 on the same endpoint before succeeding", async () => {
  const calls = [];
  const sleeps = [];
  const provider = {
    providerName: "custom",
    model: "gpt-5.4",
    baseUrl: "https://gateway.example.test/v1",
    wireApi: "responses",
    apiKey: "sk-test"
  };

  const result = await callResponsesApi(provider, "Compile this note", {
    retryBaseDelayMs: 25,
    sleepImpl: async (delayMs) => {
      sleeps.push(delayMs);
    },
    fetchImpl: async (url) => {
      calls.push(url);
      if (calls.length === 1) {
        return {
          ok: false,
          status: 524,
          text: async () => "gateway timeout"
        };
      }

      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ output_text: "[{\"wiki_kind\":\"source\",\"title\":\"Retry OK\",\"body\":\"Body\"}]" })
      };
    }
  });

  assert.equal(calls.length, 2);
  assert.deepEqual(sleeps, [100]);
  assert.equal(calls[0], "https://gateway.example.test/v1/responses");
  assert.equal(calls[1], "https://gateway.example.test/v1/responses");
  assert.equal(result.endpoint, "https://gateway.example.test/v1/responses");
});

run("responses caller aborts with a clear timeout error when the provider hangs", async () => {
  const provider = {
    providerName: "custom",
    model: "gpt-5.4",
    baseUrl: "https://gateway.example.test/v1",
    wireApi: "responses",
    apiKey: "sk-test"
  };
  let calls = 0;

  await assert.rejects(
    () =>
      callResponsesApi(provider, "Compile this note", {
        timeoutMs: 25,
        fetchImpl: async (_url, init) => {
          calls += 1;
          return await new Promise((_resolve, reject) => {
            init.signal.addEventListener(
              "abort",
              () => {
                const error = new Error("This operation was aborted");
                error.name = "AbortError";
                reject(error);
              },
              { once: true }
            );
          });
        }
      }),
    (error) => {
      assert.match(error.message, /Responses API timed out after 25ms at https:\/\/gateway\.example\.test\/v1\/responses/);
      return true;
    }
  );

  assert.equal(calls, 1);
});

run("responses caller falls back to codex exec for chatgpt auth mode", async () => {
  const provider = {
    providerName: "openai",
    model: "gpt-5.4",
    baseUrl: "https://api.openai.com/v1",
    wireApi: "responses",
    apiKey: null,
    authMode: "chatgpt",
    canUseChatGptSession: true
  };
  const calls = [];

  const result = await callResponsesApi(provider, "Compile this note", {
    spawnSyncImpl(command, args, options) {
      calls.push({ command, args, options });
      const rawArgs =
        command === "codex"
          ? args
          : String(args[args.length - 1] || "")
              .match(/"[^"]*"|[^\s]+/g)
              .map((entry) => entry.replace(/^"(.*)"$/, "$1"));
      const outputPath = rawArgs[rawArgs.indexOf("--output-last-message") + 1];
      fs.writeFileSync(outputPath, "OK from codex exec", "utf8");
      return {
        status: 0,
        stdout: "",
        stderr: ""
      };
    }
  });

  assert.equal(calls.length, 1);
  if (process.platform === "win32") {
    assert.match(calls[0].command.toLowerCase(), /cmd\.exe$/);
    assert.equal(calls[0].args[0], "/d");
    assert.match(calls[0].args[calls[0].args.length - 1], /codex exec/);
  } else {
    assert.equal(calls[0].command, "codex");
    assert.equal(calls[0].args[0], "exec");
    assert.equal(calls[0].args.includes("--ephemeral"), true);
    assert.equal(calls[0].args.includes("--skip-git-repo-check"), true);
    assert.equal(calls[0].args[calls[0].args.length - 1], "-");
  }
  assert.equal(calls[0].options.input, "Compile this note");
  assert.equal(result.endpoint, "codex exec");
  assert.equal(result.outputText, "OK from codex exec");
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
          baseUrl: "https://gateway.example.test",
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
    const logEntry = JSON.parse(fs.readFileSync(result.logFile, "utf8").trim());
    assert.equal(logEntry.provider, "custom");
    assert.equal(logEntry.model, "gpt-5.4");
    assert.match(logEntry.provider_route, /route:responses-api/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("compile output log persists provider route and endpoint context", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-compile-log-context-run-tests-"));

  try {
    const { config, rawPath } = createCompileFixture(tempRoot);
    const result = applyCompileOutput(
      config,
      {
        rawPath,
        notes: [
          {
            wiki_kind: "source",
            title: "Karpathy Route Source",
            topic: "LLM Knowledge Bases",
            body: "## Summary\n\nRoute-aware compile log.",
            source_url: "https://example.com/article"
          }
        ]
      },
      {
        timestamp: "2026-04-08T10:00:00+08:00",
        preferCli: false,
        allowFilesystemFallback: true,
        logContext: {
          provider: "openai",
          model: "gpt-5.4",
          provider_route:
            "openai | gpt-5.4 | responses | https://api.openai.com/v1 (route:codex-exec-fallback, auth-mode:chatgpt, api-key:missing)",
          provider_endpoint: "codex exec"
        }
      }
    );

    const entries = fs
      .readFileSync(result.logFile, "utf8")
      .trim()
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => JSON.parse(line));
    const lastEntry = entries.at(-1);

    assert.equal(lastEntry.provider, "openai");
    assert.equal(lastEntry.model, "gpt-5.4");
    assert.match(lastEntry.provider_route, /route:codex-exec-fallback/);
    assert.equal(lastEntry.provider_endpoint, "codex exec");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("compile execution forwards timeoutMs to provider calls and preserves error handling", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-compile-runner-timeout-"));

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
          baseUrl: "https://gateway.example.test",
          wireApi: "responses",
          apiKey: "sk-test"
        }
      },
      {
        preferCli: false,
        allowFilesystemFallback: true,
        timestamp: "2026-04-05T17:30:00+08:00",
        timeoutMs: 25,
        maxAttempts: 1,
        fetchImpl: async (_url, init) => {
          return await new Promise((_resolve, reject) => {
            const guard = setTimeout(() => {
              reject(new Error("fetch did not abort in time"));
            }, 400);
            init.signal.addEventListener(
              "abort",
              () => {
                clearTimeout(guard);
                const error = new Error("This operation was aborted");
                error.name = "AbortError";
                reject(error);
              },
              { once: true }
            );
          });
        }
      }
    );

    assert.equal(result.ok, false);
    assert.match(result.error.message, /timed out after 25ms/);

    const updatedRawFrontmatter = parseFrontmatter(
      fs.readFileSync(path.join(config.vaultPath, rawPath), "utf8")
    );
    assert.equal(updatedRawFrontmatter.status, "error");

    const logContent = fs.readFileSync(result.logFile, "utf8");
    assert.match(logContent, /"timeout_ms":25/);
    assert.match(logContent, /"provider_route":/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("compile execution falls back to a smaller prompt variant after invalid output", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-compile-runner-fallback-"));

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawPath = `${machineRoot}/10-raw/books/long-book.md`;
    const fullRawPath = path.join(vaultPath, rawPath);

    fs.mkdirSync(path.dirname(fullRawPath), { recursive: true });

    const rawFrontmatter = generateFrontmatter("raw", {
      source_type: "epub",
      topic: "LLM Knowledge Bases",
      source_url: "file:///D:/books/long-book.epub",
      captured_at: "2026-04-05T11:00:00+08:00",
      kb_date: "2026-04-05",
      status: "queued"
    });

    const content = `${rawFrontmatter}

# Long Book

## Extracted Markdown

## Part One

Long source content.
`;

    fs.writeFileSync(fullRawPath, content, "utf8");

    const config = {
      vaultPath,
      vaultName: "Test Vault",
      machineRoot,
      projectRoot: tempRoot,
      obsidian: {
        cliCandidates: [],
        exeCandidates: []
      }
    };
    const seenInputs = [];

    const result = await executeCompileForRawNote(
      config,
      {
        rawNote: {
          content,
          frontmatter: parseFrontmatter(content),
          relativePath: rawPath,
          title: "Long Book"
        },
        existingWikiNotes: [],
        templateContent: "RAW={{RAW_CONTENT}}\nTOPIC={{TOPIC}}",
        provider: {
          providerName: "custom",
          model: "gpt-5.4",
          baseUrl: "https://gateway.example.test/v1",
          wireApi: "responses",
          apiKey: "sk-test"
        },
        promptVariants: [
          {
            label: "epub-digest-80000",
            promptContent: "FIRST VARIANT"
          },
          {
            label: "epub-digest-45000",
            promptContent: "SECOND VARIANT"
          }
        ]
      },
      {
        preferCli: false,
        allowFilesystemFallback: true,
        timestamp: "2026-04-05T11:30:00+08:00",
        fetchImpl: async (_url, init) => {
          const payload = JSON.parse(init.body);
          seenInputs.push(payload.input);

          if (payload.input.includes("FIRST VARIANT")) {
            return {
              ok: true,
              status: 200,
              text: async () => JSON.stringify({ output_text: "not-json" })
            };
          }

          return {
            ok: true,
            status: 200,
            text: async () =>
              JSON.stringify({
                output_text:
                  '[{"wiki_kind":"source","title":"Fallback Source","topic":"LLM Knowledge Bases","body":"## Summary\\n\\nRecovered from smaller prompt.","source_url":"https://example.com/article"}]'
              })
          };
        }
      }
    );

    assert.equal(result.ok, true);
    assert.equal(result.promptVariant.label, "epub-digest-45000");
    assert.equal(result.attempts.length, 2);
    assert.deepEqual(
      result.attempts.map((attempt) => attempt.status),
      ["failed", "success"]
    );
    assert.equal(seenInputs.length, 2);

    const sourcePath = path.join(
      config.vaultPath,
      config.machineRoot,
      "20-wiki",
      "sources",
      "Fallback-Source.md"
    );
    assert.ok(fs.existsSync(sourcePath));

    const updatedRaw = parseFrontmatter(fs.readFileSync(path.join(config.vaultPath, rawPath), "utf8"));
    assert.equal(updatedRaw.status, "compiled");
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
