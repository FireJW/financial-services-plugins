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
  callCodexLlmWithFallback,
  describeCodexProviderRoute,
  formatCodexProviderRouteDetail,
  listCodexConfigCandidates,
  loadCodexLlmProvider,
  resolveHealthyCodexLlmProvider,
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
  selectRelevantWikiNotes,
  _resetIntentRulesCache
} from "../src/wiki-query.mjs";
import {
  createSession,
  addUserTurn,
  addAssistantTurn,
  buildConversationPrompt,
  buildEnhancedQuery,
  getLatestUserQuery,
  buildSessionTranscript,
  dumpSessionToLog
} from "../src/conversation-session.mjs";
import {
  discoverCrossTopicCandidates,
  buildCrossTopicView
} from "../src/cross-topic-discovery.mjs";
import {
  recordQueryFeedback,
  analyzeQueryFeedback
} from "../src/query-feedback.mjs";
import {
  logQueryTelemetry
} from "../src/query-telemetry.mjs";
import {
  loadXSourceRegistry,
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
  getCodexThreadBatchReviewQueuePath,
  getCodexThreadBodyDraftQueuePath,
  getCodexThreadCaptureStatusPath,
  getCodexThreadRecoveryQueuePath,
  getDashboardPath,
  getGraphTopicStatusPath,
  getKbCleanupReviewPath,
  getKbCleanupProposedMovesPath,
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
import {
  analyzeTradingReferenceCasePatterns,
  buildTradingReferencePatternCard,
  buildTradingReferenceRedFlagCard,
  listTradingReferenceCases
} from "../src/trading-reference-case-patterns.mjs";
import {
  buildTradingReferenceCaseFromRaw,
  getTradingReferenceCasePath,
  listTradingReferenceCaseCandidates,
  normalizeReferenceCaseTitle
} from "../src/trading-reference-cases.mjs";
import { buildTradingRefreshPlan } from "../src/trading-suite.mjs";
import { buildGraphTopicStatusContent, refreshWikiViews } from "../src/wiki-views.mjs";
import {
  describeProviderRoute,
  parseDoctorArgs
} from "../scripts/doctor.mjs";
import {
  executeRefreshTradingReferenceCases,
  parseRefreshTradingReferenceCasesArgs
} from "../scripts/refresh-trading-reference-cases.mjs";
import {
  parseUpgradeTradingReferenceCaseArgs,
  upgradeTradingReferenceCase
} from "../scripts/upgrade-trading-reference-case.mjs";
import {
  parseCompileSourceArgs,
  runCompileSourceProviderProbe
} from "../scripts/compile-source.mjs";
import {
  parseCaptureCodexThreadArgs,
  runCaptureCodexThread
} from "../scripts/capture-codex-thread.mjs";
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
import { parseKbCleanupReviewArgs, runKbCleanupReview } from "../scripts/kb-cleanup-review.mjs";
import { runExternalAiKbPrompt } from "../scripts/external-ai-kb-prompt.mjs";
import { runCreatePersistentCodexThreadHandoff } from "../scripts/create-persistent-codex-thread-handoff.mjs";
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
import {
  buildTradingPlanPrompt,
  buildTradingPlanRetrievalQuery,
  normalizeTradingPlanStyle,
  parseDraftTradingPlanArgs
} from "../scripts/draft-trading-plan.mjs";
import {
  buildLegendaryWorkbenchJsonExport,
  buildLegendaryWorkbenchPrompt,
  buildLegendaryWorkbenchQuery,
  buildRunReport,
  collectRequiredNotes,
  parseLegendaryWorkbenchArgs,
  resolveLegendaryWorkbenchJsonPath
} from "../scripts/legendary-investor-workbench.mjs";
import {
  loadLegendaryInvestorChecklistState,
  parseLegendaryInvestorChecklistArgs,
  resolveLegendaryInvestorChecklistStatePath,
  resolveLegendaryInvestorChecklistSourcePath,
  runLegendaryInvestorChecklist,
  writeLegendaryInvestorChecklistState
} from "../scripts/legendary-investor-checklist.mjs";
import {
  loadLegendaryDecisionFacts,
  parseLegendaryInvestorDecisionArgs,
  resolveLegendaryInvestorDecisionOutputPath,
  resolveLegendaryInvestorDecisionSourcePath,
  runLegendaryInvestorDecision,
  writeLegendaryInvestorDecisionJson
} from "../scripts/legendary-investor-decision.mjs";
import {
  loadLegendaryReviewFacts,
  parseLegendaryInvestorReviewArgs,
  resolveLegendaryInvestorReviewOutputPath,
  resolveLegendaryInvestorReviewSourcePath,
  runLegendaryInvestorReview,
  writeLegendaryInvestorReviewJson
} from "../scripts/legendary-investor-review.mjs";
import {
  parseLegendaryInvestorDashboardArgs,
  runLegendaryInvestorDashboard
} from "../scripts/legendary-investor-dashboard.mjs";
import {
  parseLegendaryInvestorRunnerArgs,
  runLegendaryInvestorRunner
} from "../scripts/legendary-investor-runner.mjs";
import {
  parseDailyValidationArgs,
  runDailyValidationCli
} from "../scripts/legendary-investor-daily-validation.mjs";
import {
  buildIntradayFacts,
  buildPostcloseFacts,
  buildValidationRecord,
  runDailyValidation,
  renderValidationRecord
} from "../src/legendary-investor-daily-validation.mjs";
import {
  aggregateValidationRecords,
  loadValidationRecords,
  renderValidationLedger
} from "../src/legendary-investor-validation-ledger.mjs";
import {
  analyzeTradingPlan,
  buildLegendaryStageFallback,
  buildRoundtableCommittee
} from "../src/legendary-investor-reasoner.mjs";
import {
  applyChecklistState,
  buildLegendaryInvestorChecklist,
  normalizeChecklistState,
  renderLegendaryInvestorChecklist
} from "../src/legendary-investor-checklist.mjs";
import {
  buildLegendaryInvestorDecision,
  renderLegendaryInvestorDecision
} from "../src/legendary-investor-decision.mjs";
import {
  buildLegendaryArtifactTitle,
  resolveLegendarySelectedNotes,
  writeLegendaryArtifactSynthesis
} from "../src/legendary-investor-writeback.mjs";
import {
  buildLegendaryInvestorReview,
  renderLegendaryInvestorReview
} from "../src/legendary-investor-review.mjs";
import {
  buildLegendaryInvestorDashboard,
  renderLegendaryInvestorDashboard
} from "../src/legendary-investor-dashboard.mjs";
import {
  getLegendaryDoctrine,
  renderDoctrineLine
} from "../src/legendary-investor-doctrines.mjs";
import {
  executeTradingPsychologyMentor,
  parseTradingPsychologyMentorArgs
} from "../scripts/trading-psychology-mentor.mjs";

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

run("compile-source parser recognizes include-error mode", () => {
  const parsed = parseCompileSourceArgs(["--file", "08-AI鐭ヨ瘑搴?10-raw/manual/demo.md", "--execute", "--include-error"]);
  assert.equal(parsed.file, "08-AI鐭ヨ瘑搴?10-raw/manual/demo.md");
  assert.equal(parsed.execute, true);
  assert.equal(parsed.includeError, true);
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
    topic: "grid combo trade card",
    title: "2026-04-08 grid combo trade card",
    body: "trade card body"
  });

  assert.equal(request.sourceType, "manual");
  assert.equal(request.topic, "grid combo trade card");
  assert.equal(request.sourceUrl, "codex://threads/019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab");
  assert.match(request.body, /trade card body/);
});

run("capture-codex-thread parser recognizes compile mode and thread id", () => {
  const parsed = parseCaptureCodexThreadArgs([
    "--thread-id",
    "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    "--topic",
    "grid combo trade card",
    "--title",
    "trade card title",
    "--compile",
    "--timeout-ms",
    "240000"
  ]);

  assert.equal(parsed.threadId, "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab");
  assert.equal(parsed.compile, true);
  assert.equal(parsed.timeoutMs, 240000);
});

run("capture-codex-thread parser recognizes skip-reference-refresh", () => {
  const parsed = parseCaptureCodexThreadArgs([
    "--thread-id",
    "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
    "--topic",
    "trading psychology",
    "--title",
    "2026-04-10 浜ゆ槗澶嶇洏",
    "--skip-reference-refresh"
  ]);

  assert.equal(parsed.skipReferenceRefresh, true);
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

run("capture-codex-thread auto-promotes trading psychology captures", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-auto-promote-"));

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

    let promotedRawPath = "";
    let patternRefreshCalls = 0;
    let rebuildLinksCalls = 0;
    let refreshViewsCalls = 0;

    const result = await runCaptureCodexThread(
      [
        "--thread-id",
        "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
        "--topic",
        "trading psychology",
        "--title",
        "2026-04-10 浜ゆ槗澶嶇洏"
      ],
      {
        config,
        readTextFromStdin: async () =>
          [
            "## User Request",
            "",
            "This is a FOMO trade review.",
            "",
            "## Assistant Response",
            "",
            "### Summary",
            "",
            "This is a classic trading psychology mistake."
          ].join("\n"),
        refreshTradingReferenceCasesImpl: (command) => {
          promotedRawPath = command.rawNote;
          return {
            ok: true,
            status: "created",
            path: "08-ai-kb/30-views/10-Trading Psychology Mentor/03-Reference Cases/2026-04-10-浜ゆ槗澶嶇洏閫愭潯瀵圭収.md"
          };
        },
        refreshTradingReferenceCasePatternArtifactsImpl: () => {
          patternRefreshCalls += 1;
          return {
            analyzedCases: 2
          };
        },
        rebuildLinksFn: () => {
          rebuildLinksCalls += 1;
          return { updated: 1, scanned: 1 };
        },
        refreshViewsFn: () => {
          refreshViewsCalls += 1;
          return [{ path: "08-ai-kb/30-views/00-System/00-KB Dashboard.md" }];
        }
      }
    );

    assert.equal(promotedRawPath, result.ingestResult.path);
    assert.ok(result.referenceRefreshResult);
    assert.ok(result.patternRefreshResult);
    assert.equal(patternRefreshCalls, 1);
    assert.equal(rebuildLinksCalls, 0);
    assert.equal(refreshViewsCalls, 0);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("capture-codex-thread skip-reference-refresh falls back to regular link and view refresh", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-skip-promote-"));

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

    let promotionCalls = 0;
    let patternRefreshCalls = 0;
    let rebuildLinksCalls = 0;
    let refreshViewsCalls = 0;

    const result = await runCaptureCodexThread(
      [
        "--thread-id",
        "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab",
        "--topic",
        "trading psychology",
        "--title",
        "2026-04-10 浜ゆ槗澶嶇洏",
        "--skip-reference-refresh"
      ],
      {
        config,
        readTextFromStdin: async () =>
          [
            "## User Request",
            "",
            "This is a FOMO trade review.",
            "",
            "## Assistant Response",
            "",
            "### Summary",
            "",
            "This is a classic trading psychology mistake."
          ].join("\n"),
        refreshTradingReferenceCasesImpl: () => {
          promotionCalls += 1;
          return { ok: true };
        },
        refreshTradingReferenceCasePatternArtifactsImpl: () => {
          patternRefreshCalls += 1;
          return { analyzedCases: 1 };
        },
        rebuildLinksFn: () => {
          rebuildLinksCalls += 1;
          return { updated: 1, scanned: 1 };
        },
        refreshViewsFn: () => {
          refreshViewsCalls += 1;
          return [{ path: "08-ai-kb/30-views/00-System/00-KB Dashboard.md" }];
        }
      }
    );

    assert.equal(promotionCalls, 0);
    assert.equal(patternRefreshCalls, 0);
    assert.equal(rebuildLinksCalls, 1);
    assert.equal(refreshViewsCalls, 1);
    assert.equal(result.referenceRefreshResult, null);
    assert.equal(result.patternRefreshResult, null);
    assert.ok(result.linkResult);
    assert.ok(Array.isArray(result.viewResults));
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

run("capture-codex-thread-batch parser recognizes skip-reference-refresh", () => {
  const parsed = parseCaptureCodexThreadBatchArgs([
    "--manifest",
    "examples/codex-thread-batch.template.json",
    "--skip-reference-refresh"
  ]);

  assert.equal(parsed.skipReferenceRefresh, true);
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
    "閹靛綊鍣哄▽澶嬬┅",
    "--title-prefix",
    "閸樺棗褰剁痪璺ㄢ柤",
    "--no-compile"
  ]);

  assert.match(parsed.outputDir, /codex-batch$/);
  assert.equal(parsed.threadIds.length, 1);
  assert.equal(parsed.threadUris.length, 1);
  assert.equal(parsed.topic, "閹靛綊鍣哄▽澶嬬┅");
  assert.equal(parsed.titlePrefix, "閸樺棗褰剁痪璺ㄢ柤");
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
      topic: "閹靛綊鍣哄▽澶嬬┅",
      titlePrefix: "閸樺棗褰剁痪璺ㄢ柤",
      sourceLabel: "Codex batch import",
      compile: true
    });

    assert.equal(plan.entries.length, 2);
    assert.equal(plan.manifest.defaults.compile, true);
    assert.equal(plan.manifest.entries[0].topic, "閹靛綊鍣哄▽澶嬬┅");
    assert.match(plan.entries[0].bodyPath, /bodies/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("init-codex-thread-batch premarks likely trading reference candidates in the manifest", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-init-codex-thread-batch-trading-hint-"));

  try {
    const plan = buildCodexThreadBatchInitPlan({
      outputDir: path.join(tempRoot, "out"),
      threadsFile: "",
      threadUris: [],
      threadIds: ["019d5746-28de-7631-ad1c-d35ca5815b94"],
      topic: "trading psychology",
      titlePrefix: "浜ゆ槗澶嶇洏",
      sourceLabel: "Codex batch import",
      compile: true
    });

    assert.equal(plan.entries.length, 1);
    assert.equal(plan.manifest.entries[0].reference_case_candidate, "likely");
    assert.deepEqual(plan.manifest.entries[0].candidate_tags, [
      "trading-psychology-reference-case"
    ]);
    assert.match(
      plan.manifest.entries[0].review_hint,
      /Likely trading psychology/
    );
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
        "閹靛綊鍣哄▽澶嬬┅",
        "--title-prefix",
        "閸樺棗褰剁痪璺ㄢ柤"
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
    assert.match(writes.join("\n"), /Likely trading reference candidates:/);
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
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "濞村鐦稉濠氼暯"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n\n## Thread Source\n\n- thread_uri: codex://threads/thread-a\n`,
      "utf8"
    );

    fs.writeFileSync(
      wikiPath,
      `---\nkb_type: "wiki"\nwiki_kind: "source"\ntopic: "濞村鐦稉濠氼暯"\ncompiled_from: ["08-AI閻儴鐦戞惔?10-raw/manual/Thread-A.md"]\ncompiled_at: "2026-04-08T00:05:00+08:00"\nkb_date: "2026-04-08"\nreview_state: "draft"\nmanaged_by: "codex"\nkb_source_count: 1\ndedup_key: "濞村鐦稉濠氼暯::source::codex://threads/thread-a"\n---\n\n# Thread A Source\n`,
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
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "濞村鐦稉濠氼暯"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n`,
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
    "鐞涖儱缍嶆稉濠氼暯",
    "--title-prefix",
    "Missing Thread",
    "--no-compile"
  ]);

  assert.match(parsed.outputDir, /reconcile$/);
  assert.equal(parsed.threadIds.length, 1);
  assert.equal(parsed.topic, "鐞涖儱缍嶆稉濠氼暯");
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
      `---\nkb_type: "raw"\nsource_type: "manual"\ntopic: "濞村鐦稉濠氼暯"\nsource_url: "codex://threads/thread-a"\ncaptured_at: "2026-04-08T00:00:00+08:00"\nkb_date: "2026-04-08"\nstatus: "compiled"\nmanaged_by: "human"\n---\n\n# Thread A\n`,
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
        topic: "鐞涖儱缍嶆稉濠氼暯",
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

run("kb-cleanup-review parser recognizes json mode", () => {
  const parsed = parseKbCleanupReviewArgs(["--json"]);
  assert.equal(parsed.json, true);
});

run("kb-cleanup-review reports proposed moves in text mode", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-kb-cleanup-review-"));
  const writes = [];

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

    const manualDir = path.join(config.vaultPath, config.machineRoot, "10-raw", "manual");
    const archiveDir = path.join(config.vaultPath, config.machineRoot, "99-archive");
    fs.mkdirSync(manualDir, { recursive: true });
    fs.mkdirSync(path.join(archiveDir, "encoding-quarantine"), { recursive: true });
    fs.mkdirSync(path.join(archiveDir, "validation-false-positives"), { recursive: true });
    fs.writeFileSync(path.join(manualDir, "2026-04-08-Codex-batch-smoke-A.md"), "# smoke\n", "utf8");

    const review = runKbCleanupReview([], {
      config,
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      }
    });

    assert.equal(review.manualRawCount, 1);
    assert.match(writes.join("\n"), /KB Cleanup Review/);
    assert.match(writes.join("\n"), /Proposed moves:/);
    assert.match(writes.join("\n"), /Dry-run plan:/);
    assert.match(writes.join("\n"), /Codex-batch-smoke-A/);
    assert.match(writes.join("\n"), /WhatIf/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("external-ai-kb-prompt prints the handoff prompt document", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-external-ai-kb-prompt-"));
  const promptPath = path.join(tempRoot, "external-ai-kb-handoff-prompt.zh-CN.md");
  const writes = [];

  try {
    fs.writeFileSync(
      promptPath,
      "# External AI KB Handoff Prompt\n\nUse `doctor` first.\n",
      "utf8"
    );

    const result = runExternalAiKbPrompt({
      promptPath,
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      }
    });

    assert.match(result.promptPath, /external-ai-kb-handoff-prompt\.zh-CN\.md$/);
    assert.match(result.content, /External AI KB Handoff Prompt/);
    assert.match(writes.join("\n"), /doctor/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("create-persistent-codex-thread-handoff creates a stable handoff workspace", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-persistent-codex-thread-handoff-"));
  const writes = [];

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

    const plan = runCreatePersistentCodexThreadHandoff({
      config,
      writer: {
        log(line = "") {
          writes.push(String(line));
        }
      }
    });

    assert.match(plan.manifestPath, /handoff[\\/]codex-thread-batches[\\/]persistent-trading-psychology[\\/]manifest\.json$/);
    assert.equal(fs.existsSync(plan.manifestPath), true);
    assert.equal(plan.entries.length, 2);
    assert.equal(plan.manifest.entries[0].thread_uri, "codex://threads/trading-psychology-2026-04-07");
    assert.equal(plan.manifest.entries[1].thread_uri, "codex://threads/trading-psychology-2026-04-09");
    assert.match(plan.manifest.entries[0].title, /2026-04-07/);
    assert.match(plan.manifest.entries[1].title, /2026-04-09/);
    assert.match(fs.readFileSync(plan.entries[0].bodyPath, "utf8"), /## User Request/);
    assert.match(fs.readFileSync(plan.entries[1].bodyPath, "utf8"), /鍋滅伀鑴嗗急鎬т笌鍗栭妯″紡澶嶇洏/);
    assert.doesNotMatch(
      fs.readFileSync(plan.entries[0].bodyPath, "utf8"),
      /鐠囬攱濡竱閸嬫粎浼€|閼昏京娣畖娴溿倖妲?
    );
    assert.doesNotMatch(fs.readFileSync(plan.entries[0].bodyPath, "utf8"), /\[Paste the user request/);
    assert.match(writes.join("\n"), /Persistent handoff manifest:/);
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
            topic: "batch import",
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
            path: `08-AI閻儴鐦戞惔?10-raw/manual/${entry.title}.md`,
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
            path: "08-AI閻儴鐦戞惔?20-wiki/_index.md",
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

run("codex thread batch auto-promotes trading psychology captures and refreshes pattern card once", async () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-codex-thread-batch-promote-"));
  const writes = [];
  const captures = [];

  try {
    const summary = await runCaptureCodexThreadBatch(
      {
        manifestPath: "ignored.json",
        compile: false,
        skipLinks: false,
        skipViews: false,
        skipReferenceRefresh: false,
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
              threadUri: "codex://threads/trading-a",
              topic: "trading psychology",
              title: "2026-04-10 浜ゆ槗澶嶇洏 A",
              body: [
                "## User Request",
                "",
                "This is a FOMO chase review.",
                "",
                "## Assistant Response",
                "",
                "### Summary",
                "",
                "This is a classic trading psychology mistake."
              ].join("\n"),
              compile: false
            },
            {
              threadUri: "codex://threads/non-trading-b",
              topic: "macro research",
              title: "2026-04-10 瀹忚鐮旂┒璁板綍",
              body: [
                "## User Request",
                "",
                "Record today's macro observation.",
                "",
                "## Assistant Response",
                "",
                "This is mainly a research memo, not a trading psychology case."
              ].join("\n"),
              compile: false
            }
          ]
        },
        writer: {
          log(line = "") {
            writes.push(String(line));
          },
          error() {}
        },
        captureFn: async (_config, entry, options) => {
          captures.push({
            title: entry.title,
            skipLinks: options.skipLinks,
            skipViews: options.skipViews
          });
          return {
            ingestResult: {
              path: `08-ai-kb/10-raw/manual/${entry.title}.md`,
              mode: "filesystem-fallback"
            },
            compileResult: null
          };
        },
        refreshTradingReferenceCasesImpl: (command) => ({
          ok: true,
          status: "created",
          path: `08-ai-kb/30-views/10-Trading Psychology Mentor/03-Reference Cases/${path.basename(
            command.rawNote
          )}`
        }),
        refreshTradingReferenceCasePatternArtifactsImpl: () => ({
          analyzedCases: 4,
          linkResult: {
            updated: 5,
            scanned: 20
          },
          viewResults: [
            {
              path: "08-ai-kb/30-views/10-Trading Psychology Mentor/00-Index.md",
              mode: "filesystem-fallback"
            }
          ]
        }),
        rebuildLinksFn() {
          throw new Error("regular link refresh should not run when pattern refresh owns finalization");
        },
        refreshViewsFn() {
          throw new Error("regular view refresh should not run when pattern refresh owns finalization");
        }
      }
    );

    assert.equal(summary.total, 2);
    assert.equal(summary.completed, 2);
    assert.equal(summary.failed, 0);
    assert.equal(summary.patternRefreshResult.analyzedCases, 4);
    assert.equal(summary.linkResult.updated, 5);
    assert.equal(summary.viewResults.length, 1);
    assert.deepEqual(
      captures.map((entry) => [entry.title, entry.skipLinks, entry.skipViews]),
      [
        ["2026-04-10 浜ゆ槗澶嶇洏 A", true, true],
        ["2026-04-10 瀹忚鐮旂┒璁板綍", true, true]
      ]
    );
    assert.match(writes.join("\n"), /Reference case refresh: created/);
    assert.match(writes.join("\n"), /Pattern card refresh: analyzed 4 reference case\(s\)/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
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
        relativePath: `08-AI閻儴鐦戞惔?10-raw/manual/raw-${index + 1}.md`,
        frontmatter: {
          source_type: "manual",
          source_url: `https://example.com/raw-${index + 1}`,
          captured_at: "2026-04-08T00:00:00+08:00"
        },
        content: `---\nkb_type: "raw"\n---\n\n${largeBody}`
      })),
      wikiNotes: Array.from({ length: 8 }, (_, index) => ({
        title: `Wiki ${index + 1}`,
        relativePath: `08-AI閻儴鐦戞惔?20-wiki/concepts/wiki-${index + 1}.md`,
        frontmatter: {
          wiki_kind: "concept",
          compiled_from: [`08-AI閻儴鐦戞惔?10-raw/manual/raw-${(index % 6) + 1}.md`]
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
      path: "08-ai-kb/20-wiki/sources/A-reference-map.md"
    },
    {
      path: "08-ai-kb/20-wiki/sources/B-reference-map.md"
    },
    {
      path: "08-ai-kb/20-wiki/sources/A-reference-map.md"
    },
    {
      path: "08-ai-kb/10-raw/books/ignored.md"
    }
  ]);

  assert.deepEqual(compiledFrom, [
    "08-ai-kb/20-wiki/sources/A-reference-map.md",
    "08-ai-kb/20-wiki/sources/B-reference-map.md"
  ]);
});

run("reference hub repair extracts linked wiki notes from Book Maps section", () => {
  const body = `# Finance Book Reference Hub

## Book Maps

  - [[08-ai-kb/20-wiki/sources/A-reference-map|A]]
  - [[08-ai-kb/20-wiki/sources/B-reference-map|B]]

## Search Seeds

- ignored
`;

  assert.deepEqual(extractLinkedWikiPathsFromSection(body, "Book Maps"), [
    "08-ai-kb/20-wiki/sources/A-reference-map.md",
    "08-ai-kb/20-wiki/sources/B-reference-map.md"
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
      "refresh-trading-reference-cases",
      "refresh-trading-reference-case-pattern-card",
      "refresh-wiki-views",
      "health-check"
    ]
  );
  assert.equal(noHealthPlan.at(-1).id, "refresh-wiki-views");
});

run("trading reference case pattern analysis extracts recurring modes from reference cases", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-trading-reference-cases-"));

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const referenceDir = path.join(
      vaultPath,
      machineRoot,
      "30-views",
      "10-Trading Psychology Mentor",
      "03-Reference Cases"
    );
    fs.mkdirSync(referenceDir, { recursive: true });

    fs.writeFileSync(
      path.join(referenceDir, "2026-04-07-trade-review-reference.md"),
      `# 2026-04-07 trade review reference

## Common Mistakes and Fixes
- Timeframe drift
- Prediction vs confirmation mismatch
- Static target anchoring
- Trial position upgraded into long-term hold`,
      "utf8"
    );

    fs.writeFileSync(
      path.join(referenceDir, "2026-04-09-ceasefire-review-reference.md"),
      `# 2026-04-09 ceasefire review reference

## Core Conclusions

Leading the market then doubting yourself. Direction right, expression wrong. Selling without type labels turns exits into emotional pain relief. Ceasefire, oil, power grid, and empty-book anxiety got mixed into one substitute trade.`,
      "utf8"
    );

    const cases = listTradingReferenceCases(vaultPath, machineRoot);
    const analysis = analyzeTradingReferenceCasePatterns(cases);
    const markdown = buildTradingReferencePatternCard({
      cases,
      analysis,
      generatedAt: "2026-04-10T08:00:00+08:00"
    });
    const redFlagMarkdown = buildTradingReferenceRedFlagCard({
      analysis,
      generatedAt: "2026-04-10T08:00:00+08:00"
    });

    assert.equal(cases.length, 2);
    assert.equal(analysis.totalCases, 2);
    assert.ok(Array.isArray(analysis.patternSummaries));
    assert.match(markdown, /Reference Cases/);
    assert.match(markdown, /2026-04-09-ceasefire-review-reference/);
    assert.match(redFlagMarkdown, /Reference Cases/);
    assert.match(redFlagMarkdown, /Trading Pattern Card|Reference Cases/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("trading reference case title normalization appends suffix only once", () => {
  assert.equal(
    normalizeReferenceCaseTitle("2026-04-09-trading-review"),
    "2026-04-09-trading-review逐条对照"
  );
  assert.equal(
    normalizeReferenceCaseTitle("2026-04-09-trading-review逐条对照.md"),
    "2026-04-09-trading-review逐条对照"
  );
  assert.equal(
    getTradingReferenceCasePath("08-ai-kb", "2026-04-09-trading-review"),
    "08-ai-kb/30-views/10-Trading Psychology Mentor/03-Reference Cases/2026-04-09-trading-review逐条对照.md"
  );
});

run("buildTradingReferenceCaseFromRaw upgrades a raw mentor note into a linked reference case", () => {
  const tempRoot = fs.mkdtempSync(
    path.join(process.cwd(), ".tmp-build-trading-reference-case-")
  );

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawRelativePath = `${machineRoot}/10-raw/manual/2026-04-09-trading-review.md`;
    const rawAbsolutePath = path.join(vaultPath, rawRelativePath);
    const conceptPath = `${machineRoot}/20-wiki/concepts/trade-log-template.md`;
    const synthesisPath = `${machineRoot}/20-wiki/syntheses/pre-open-red-flags.md`;
    const otherRawPath = `${machineRoot}/10-raw/manual/2026-04-08-grid-combo-trade-card.md`;
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

    fs.mkdirSync(path.dirname(rawAbsolutePath), { recursive: true });
    fs.mkdirSync(path.join(vaultPath, machineRoot, "20-wiki", "concepts"), { recursive: true });
    fs.mkdirSync(path.join(vaultPath, machineRoot, "20-wiki", "syntheses"), { recursive: true });

    fs.writeFileSync(path.join(vaultPath, conceptPath), "# trade-log-template\n\nBody\n", "utf8");
    fs.writeFileSync(path.join(vaultPath, synthesisPath), "# pre-open-red-flags\n\nBody\n", "utf8");
    fs.writeFileSync(
      path.join(vaultPath, otherRawPath),
      "# 2026-04-08-grid-combo-trade-card\n\nBody\n",
      "utf8"
    );

    const rawFrontmatter = generateFrontmatter("raw", {
      source_type: "manual",
      topic: "trading psychology",
      source_url: "",
      captured_at: "2026-04-10T09:30:00+08:00",
      kb_date: "2026-04-10",
      status: "queued"
    });
    fs.writeFileSync(
      rawAbsolutePath,
      `${rawFrontmatter}

# 2026-04-09-trading-review

## User Request

- Deep review this two-day trading sequence.
- Persist the result into the knowledge base.

## Assistant Response

### 总判断
You did not lose the direction, you ended the expression too early.

### Deep Dive

Read these together:

- [[08-ai-kb/10-raw/manual/2026-04-08-grid-combo-trade-card]]
- [[08-ai-kb/20-wiki/concepts/trade-log-template]]
- [[08-ai-kb/20-wiki/syntheses/pre-open-red-flags]]
- [[08-ai-kb/10-raw/manual/2026-04-09-trading-review]]

The better move is to split the leading-position tranche from the confirmation tranche.
`,
      "utf8"
    );

    const result = buildTradingReferenceCaseFromRaw(config, {
      rawRelativePath
    });

    assert.equal(
      result.path,
      "08-ai-kb/30-views/10-Trading Psychology Mentor/03-Reference Cases/2026-04-09-trading-review逐条对照.md"
    );
    assert.match(result.content, /## 说明/);
    assert.match(result.content, /## 联动阅读/);
    assert.match(
      result.content,
      /\[\[08-ai-kb\/10-raw\/manual\/2026-04-08-grid-combo-trade-card\|2026-04-08-grid-combo-trade-card\]\]/
    );
    assert.match(
      result.content,
      /\[\[08-ai-kb\/20-wiki\/concepts\/trade-log-template\|trade-log-template\]\]/
    );
    assert.match(
      result.content,
      /\[\[08-ai-kb\/20-wiki\/syntheses\/pre-open-red-flags\|pre-open-red-flags\]\]/
    );
    assert.match(result.content, /## 导师总判断/);
    assert.match(result.content, /You did not lose the direction/);
    assert.match(result.content, /## 深度复盘正文/);
    assert.equal(result.relatedPaths.length >= 4, true);
    assert.doesNotMatch(result.content, /璇锋妸|鍋滅伀|鑻辩淮|浜ゆ槗/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("buildTradingReferenceCaseFromRaw also supports mentor raw captures", () => {
  const tempRoot = fs.mkdtempSync(
    path.join(process.cwd(), ".tmp-build-trading-reference-case-mentor-")
  );

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawRelativePath = `${machineRoot}/10-raw/manual/Trading-Psychology-Mentor-Raw-2026-04-10.md`;
    const rawAbsolutePath = path.join(vaultPath, rawRelativePath);
    const sourceNotePath = `${machineRoot}/20-wiki/syntheses/trading-psychology-pattern-card.md`;
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

    fs.mkdirSync(path.dirname(rawAbsolutePath), { recursive: true });
    fs.mkdirSync(path.dirname(path.join(vaultPath, sourceNotePath)), { recursive: true });
    fs.writeFileSync(
      path.join(vaultPath, sourceNotePath),
      "# trading-psychology-pattern-card\n\nBody\n",
      "utf8"
    );

    fs.writeFileSync(
      rawAbsolutePath,
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "trading psychology",
        source_url: "mentor://trading-psychology-session",
        captured_at: "2026-04-10T10:30:00+08:00",
        kb_date: "2026-04-10",
        status: "queued"
      })}

# Trading Psychology Mentor Raw - 2026-04-10

## User Query

Review why I chased the breakout today.

## Practice Context

- I wanted to add too early before confirmation.

## Mentor Response

### 总判断
Your problem was not the read, it was oversizing before confirmation.

### Better Alternative

- Keep the starter position small, then wait for confirmation.

## Source Notes

- [[08-ai-kb/20-wiki/syntheses/trading-psychology-pattern-card]]
`,
      "utf8"
    );

    const result = buildTradingReferenceCaseFromRaw(config, {
      rawRelativePath
    });

    assert.match(result.content, /## 原始请求摘要/);
    assert.match(result.content, /Review why I chased the breakout today\./);
    assert.match(result.content, /I wanted to add too early before confirmation\./);
    assert.match(result.content, /## 导师总判断/);
    assert.match(result.content, /oversizing before confirmation/);
    assert.match(
      result.content,
      /\[\[08-ai-kb\/20-wiki\/syntheses\/trading-psychology-pattern-card\|trading-psychology-pattern-card\]\]/
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("listTradingReferenceCaseCandidates keeps only eligible trading raw notes", () => {
  const tempRoot = fs.mkdtempSync(
    path.join(process.cwd(), ".tmp-list-trading-reference-case-candidates-")
  );

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
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
    const manualDir = path.join(vaultPath, machineRoot, "10-raw", "manual");
    fs.mkdirSync(manualDir, { recursive: true });

    fs.writeFileSync(
      path.join(manualDir, "2026-04-10-trade-review.md"),
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "trading psychology",
        source_url: "",
        captured_at: "2026-04-10T11:00:00+08:00",
        kb_date: "2026-04-10",
        status: "queued"
      })}

# 2026-04-10-trade-review

## User Request

- Review today's trade and the FOMO response.

## Assistant Response

### 总判断
Write it down before it fades.
`,
      "utf8"
    );

    fs.writeFileSync(
      path.join(manualDir, "2026-04-10-knowledge-note.md"),
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "workflow",
        source_url: "",
        captured_at: "2026-04-10T11:05:00+08:00",
        kb_date: "2026-04-10",
        status: "queued"
      })}

# 2026-04-10-knowledge-note

## User Request

- Summarize this workflow.

## Assistant Response

### 总判断
Keep organizing the doc.
`,
      "utf8"
    );

    fs.writeFileSync(
      path.join(manualDir, "Trading-Psychology-Mentor-Raw-workflow-dry-run.md"),
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "trading psychology",
        source_url: "mentor://trading-psychology-session",
        captured_at: "2026-04-10T11:06:00+08:00",
        kb_date: "2026-04-10",
        status: "queued"
      })}

# Trading Psychology Mentor Raw - workflow dry run

## User Query

Please test the workflow.

## Mentor Response

### 总判断
This is a workflow dry run and should not be promoted.
`,
      "utf8"
    );

    const candidates = listTradingReferenceCaseCandidates(config);
    assert.equal(candidates.length, 1);
    assert.equal(
      candidates[0].rawRelativePath,
      "08-ai-kb/10-raw/manual/2026-04-10-trade-review.md"
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("upgrade-trading-reference-case parser recognizes overwrite and skip flags", () => {
  const parsed = parseUpgradeTradingReferenceCaseArgs([
    "--raw-note",
    "08-ai-kb/10-raw/manual/2026-04-09-trading-review.md",
    "--title",
    "2026-04-09-trading-review",
    "--overwrite",
    "--skip-links",
    "--skip-views"
  ]);

  assert.equal(parsed.rawNote, "08-ai-kb/10-raw/manual/2026-04-09-trading-review.md");
  assert.equal(parsed.title, "2026-04-09-trading-review");
  assert.equal(parsed.overwrite, true);
  assert.equal(parsed.skipLinks, true);
  assert.equal(parsed.skipViews, true);
});

run("upgradeTradingReferenceCase skips an existing case unless overwrite is enabled", () => {
  const tempRoot = fs.mkdtempSync(
    path.join(process.cwd(), ".tmp-upgrade-trading-reference-case-")
  );

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
    const rawRelativePath = `${machineRoot}/10-raw/manual/2026-04-09-trading-review.md`;
    const rawAbsolutePath = path.join(vaultPath, rawRelativePath);
    const existingReferencePath = `${machineRoot}/30-views/10-Trading Psychology Mentor/03-Reference Cases/2026-04-09-trading-review逐条对照.md`;
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

    fs.mkdirSync(path.dirname(rawAbsolutePath), { recursive: true });
    fs.mkdirSync(path.dirname(path.join(vaultPath, existingReferencePath)), {
      recursive: true
    });

    fs.writeFileSync(
      rawAbsolutePath,
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "trading psychology",
        source_url: "",
        captured_at: "2026-04-10T09:30:00+08:00",
        kb_date: "2026-04-10",
        status: "queued"
      })}

# 2026-04-09-trading-review

## User Request

- Review this trading sequence.

## Assistant Response

### 总判断
Write it down first.
`,
      "utf8"
    );

    fs.writeFileSync(
      path.join(vaultPath, existingReferencePath),
      "# Existing final draft\n",
      "utf8"
    );

    const skipped = upgradeTradingReferenceCase(
      {
        rawNote: rawRelativePath,
        title: "",
        overwrite: false,
        skipLinks: true,
        skipViews: true
      },
      { config }
    );

    assert.equal(skipped.skipped, true);
    assert.equal(skipped.reason, "reference_case_exists");

    const overwritten = upgradeTradingReferenceCase(
      {
        rawNote: rawRelativePath,
        title: "",
        overwrite: true,
        skipLinks: true,
        skipViews: true
      },
      { config }
    );

    assert.equal(overwritten.ok, true);
    assert.equal(overwritten.skipped, false);
    const nextContent = fs.readFileSync(path.join(vaultPath, existingReferencePath), "utf8");
    assert.match(nextContent, /# 2026-04-09-trading-review逐条对照/);
    assert.match(nextContent, /## Source Raw/);
    assert.doesNotMatch(nextContent, /\uFFFD/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("refresh-trading-reference-cases parser keeps optional raw-note mode and skip flags", () => {
  const parsed = parseRefreshTradingReferenceCasesArgs([
    "--raw-note",
    "08-AI鐭ヨ瘑搴?10-raw/manual/2026-04-09-鍋滅伀鑴嗗急鎬с€侀鍏堝競鍦轰笌鍗栭妯″紡澶嶇洏.md",
    "--overwrite",
    "--skip-links",
    "--skip-views"
  ]);

  assert.equal(
    parsed.rawNote,
    "08-AI鐭ヨ瘑搴?10-raw/manual/2026-04-09-鍋滅伀鑴嗗急鎬с€侀鍏堝競鍦轰笌鍗栭妯″紡澶嶇洏.md"
  );
  assert.equal(parsed.overwrite, true);
  assert.equal(parsed.skipLinks, true);
  assert.equal(parsed.skipViews, true);
});

run("refresh-trading-reference-cases creates missing cases and skips unrelated manual notes", () => {
  const tempRoot = fs.mkdtempSync(
    path.join(process.cwd(), ".tmp-refresh-trading-reference-cases-")
  );

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
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
    const manualDir = path.join(vaultPath, machineRoot, "10-raw", "manual");
    fs.mkdirSync(manualDir, { recursive: true });

    fs.writeFileSync(
      path.join(manualDir, "2026-04-10-trade-review.md"),
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "trading psychology",
        source_url: "",
        captured_at: "2026-04-10T11:00:00+08:00",
        kb_date: "2026-04-10",
        status: "queued"
      })}

# 2026-04-10-trade-review

## User Request

- Review today's trading mistakes.
## Assistant Response

### Summary
Separate starter positions from confirmation adds.`,
      "utf8"
    );

    fs.writeFileSync(
      path.join(manualDir, "2026-04-10-ai-workflow.md"),
      `${generateFrontmatter("raw", {
        source_type: "manual",
        topic: "workflow",
        source_url: "",
        captured_at: "2026-04-10T11:05:00+08:00",
        kb_date: "2026-04-10",
        status: "queued"
      })}

# 2026-04-10-ai-workflow
## User Request

- Summarize this AI workflow.
## Assistant Response

### Summary
Keep organizing the workflow doc.`,
      "utf8"
    );

    const result = executeRefreshTradingReferenceCases(
      {
        rawNote: null,
        title: null,
        overwrite: false,
        skipLinks: true,
        skipViews: true
      },
      { config }
    );

    assert.equal(result.ok, true);
    assert.equal(result.created, 1);
    assert.equal(result.skipped, 0);
    const referencePath = path.join(
      vaultPath,
      machineRoot,
      "30-views",
      "10-Trading Psychology Mentor",
      "03-Reference Cases",
      result.results.find((item) => item.status === "created")?.referencePath || ""
    );
    assert.equal(referencePath.includes("2026-04-10-trade-review"), true);
    assert.equal(
      fs.existsSync(
        path.join(
          vaultPath,
          machineRoot,
          "30-views",
          "10-Trading Psychology Mentor",
          "03-Reference Cases",
          "2026-04-10-AI宸ヤ綔娴侀€愭潯瀵圭収.md"
        )
      ),
      false
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
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
      promoted_bucket: "08-AI閻儴鐦戞惔?10-raw/web/x-promoted",
      index_bucket: "08-AI閻儴鐦戞惔?10-raw/web/x-index",
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

run("x source registry falls back to an empty default config when the file is missing", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-x-source-registry-missing-"));

  try {
    const registryPath = path.join(tempRoot, "missing-whitelist.json");
    const registry = loadXSourceRegistry(registryPath);

    assert.equal(registry.version, 1);
    assert.equal(registry.default_policy.media_policy, "remote_only");
    assert.equal(registry.authors.length, 0);
    assert.equal(registry.default_policy.promote_to_raw, undefined);
    assert.deepEqual(registry.default_policy.promotion_rules.promote_to_raw, [
      "call_summary",
      "report_summary",
      "policy_summary",
      "macro_update",
      "important_thread"
    ]);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
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
  const paths = buildGraphifyTopicPaths("C:\\repo\\obsidian-kb-local", "娑擃厼娴楀Ч鍊熸簠閸戠儤鎹ｉ柧鎾呯窗濮ｆ柧绨规潻顏傗偓浣风瑐濮瑰鈧胶顩撮懓鈧悳鑽ゆ嫅");
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
        relativePath: "08-AI閻儴鐦戞惔?10-raw/books/Test-Book.md"
      }
    ],
    wikiNotes: [
      {
        relativePath: "08-AI閻儴鐦戞惔?20-wiki/concepts/Test-Concept.md",
        wikiKind: "concept"
      }
    ]
  });

  assert.equal(sourceMap.get("raw/Test-Book.md"), "08-AI閻儴鐦戞惔?10-raw/books/Test-Book.md");
  assert.equal(
    sourceMap.get("wiki/concept/Test-Concept.md"),
    "08-AI閻儴鐦戞惔?20-wiki/concepts/Test-Concept.md"
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
      query: "Why did I chase the breakout?",
      topic: "trading psychology",
      journalContext: "After the first stop I wanted to re-enter immediately.",
      noteContext: "### Note 1: Consistent execution beats emotional urgency."
    }
  );

  assert.match(prompt, /Why did I chase the breakout/);
  assert.match(prompt, /trading psychology/);
  assert.match(prompt, /re-enter immediately/);
  assert.match(prompt, /Consistent execution/);
});

run("trading psychology mentor session note builds mentor view note path", () => {
  const note = buildTradingPsychologyMentorSessionNote(
    {
      machineRoot: "08-ai-kb"
    },
    {
      query: "Why did I chase the breakout?",
      templateLabel: "Intraday template",
      journalContext: "Two losses in a row made me want to win it back.",
      answer: "Pause first, then re-check the invalidation rule.",
      selectedNotes: []
    }
  );

  assert.match(note.path, /30-views\/10-Trading Psychology Mentor\/01-Sessions\//);
  assert.match(note.content, /Intraday template/);
  assert.match(note.content, /Mentor Response/);
  assert.match(note.content, /Pause first/);
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
      machineRoot: "08-ai-kb"
    },
    {
      query: "Why did I chase the breakout?",
      templateLabel: "Intraday template",
      journalContext: "Two losses in a row made me want to win it back.",
      answer: "Pause first, then re-check the invalidation rule.",
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
    "08-AI鐭ヨ瘑搴?30-views/10-Trading Psychology Mentor/02-Templates/Trading Psychology Template - 鐩樹腑妯℃澘.md"
  ]);
  assert.equal(
    parsed.contextNote,
    "08-AI鐭ヨ瘑搴?30-views/10-Trading Psychology Mentor/02-Templates/Trading Psychology Template - 鐩樹腑妯℃澘.md"
  );
});

run("trading psychology mentor auto-refreshes reference cases after writing a session", async () => {
  const tempRoot = fs.mkdtempSync(
    path.join(process.cwd(), ".tmp-trading-psychology-mentor-refresh-")
  );

  try {
    const vaultPath = path.join(tempRoot, "vault");
    const machineRoot = "08-ai-kb";
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
    const wikiPath = path.join(
      vaultPath,
      machineRoot,
      "20-wiki",
      "syntheses",
      "trading-psychology-anchor.md"
    );
    fs.mkdirSync(path.dirname(wikiPath), { recursive: true });
    fs.writeFileSync(
      wikiPath,
      `${generateFrontmatter("wiki", {
        wiki_kind: "synthesis",
        topic: "trading psychology",
        compiled_from: [`${machineRoot}/10-raw/manual/source.md`],
        compiled_at: "2026-04-10T12:00:00+08:00",
        kb_date: "2026-04-10",
        review_state: "draft",
        kb_source_count: 1,
        dedup_key: "trading-psychology-anchor"
      })}

# trading-psychology-anchor

Focus on FOMO, stop losses, and add discipline.`,
      "utf8"
    );

    const refreshCalls = [];
    const patternCalls = [];
    const result = await executeTradingPsychologyMentor(
      {
        query: "Why do I always want to add before confirmation?",
        template: "",
        topic: "trading psychology",
        title: "2026-04-10 intraday add impulse",
        contextNote: null,
        dryRun: false,
        execute: true,
        writeSession: true,
        skipRawCapture: false,
        skipReferenceRefresh: false,
        writeTemplate: false,
        debugRetrieval: false,
        limit: 8
      },
      {
        config,
        journalContext: "When price starts lifting I want to turn the starter position into a full position immediately.",
        templateContent: "Q={{QUERY}}\nJ={{JOURNAL_CONTEXT}}\nN={{NOTE_CONTEXT}}",
        provider: {
          providerName: "mock",
          model: "mock-model",
          baseUrl: "https://mock.example.test/v1",
          configPath: "mock-provider.toml"
        },
        callResponsesApiImpl: async () => ({
          outputText: "### Summary\n\nYour main issue is adding before confirmation.\n\n### Deep Dive\n\nWait for confirmation before you upgrade position size.",
          endpoint: "mock-endpoint"
        }),
        refreshTradingReferenceCasesImpl: (command) => {
          refreshCalls.push(command);
          return {
            ok: true,
            created: 1,
            overwritten: 0,
            skipped: 0,
            results: [{ status: "created" }]
          };
        },
        refreshTradingReferenceCasePatternArtifactsImpl: () => {
          patternCalls.push("called");
          return {
            analyzedCases: 3,
            updated: []
          };
        }
      }
    );

    assert.ok(result.sessionResult);
    assert.ok(result.rawCaptureResult);
    assert.equal(refreshCalls.length, 1);
    assert.equal(patternCalls.length, 1);
    assert.equal(refreshCalls[0].rawNote, result.rawCaptureResult.path);
    assert.equal(refreshCalls[0].skipLinks, true);
    assert.equal(refreshCalls[0].skipViews, true);
    assert.equal(result.patternRefreshResult.analyzedCases, 3);
    assert.equal(fs.existsSync(path.join(vaultPath, result.sessionResult.path)), true);
    assert.equal(fs.existsSync(path.join(vaultPath, result.rawCaptureResult.path)), true);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("trading psychology mentor fallback response names chase and revenge patterns", () => {
  const response = buildTradingPsychologyMentorFallbackResponse({
    query: "I chased the breakout, got stopped, and then chased again.",
    journalContext: "After the stop I wanted to win it back immediately and kept staring at P&L."
  });

  assert.match(response, /What You Did Well/);
  assert.match(response, /Likely Pattern/);
  assert.match(response, /Next Drill/);
  assert.match(response, /Next Drill/);
});

run("trading psychology mentor templates resolve and build template notes", () => {
  const template = resolveTradingPsychologyMentorTemplate("premarket");
  assert.equal(template.label, "盘前模板");

  const note = buildTradingPsychologyTemplateNote(
    {
      machineRoot: "08-ai-kb"
    },
    "postmarket"
  );
  assert.match(note.path, /10-Trading Psychology Mentor\/02-Templates\//);
  assert.match(note.content, /## Query/);
  assert.match(note.content, /## 明日修正|## Practice Context/);
});

run("stdin text decoder handles utf16le chinese content from powershell pipes", () => {
  const sample = "Intraday scenario: gap up, spike, then quick fade.";
  const encoded = Buffer.from(sample, "utf16le");
  assert.equal(decodeUnknownText(encoded), sample);
});

run("trading psychology mentor fallback prefers early-add diagnosis for calm starter positions", () => {
  const response = buildTradingPsychologyMentorFallbackResponse({
    query:
      "Please focus on whether opening a tiny starter position before full confirmation, without chasing, is acceptable execution.",
    journalContext:
      "The setup was valid, I only opened a very small starter, stayed calm, and mostly felt a mild urge to add too early."
  });

  assert.match(response, /What You Did Well/);
  assert.match(response, /Better Alternative/);
  assert.match(response, /invalidat|Next Drill/i);
});
run("graphify topic fallback scores notes by keyword relevance", () => {
  const note = {
    title: "Momentum Trading Breakouts",
    relativePath: "08-AI閻儴鐦戞惔?10-raw/books/Momentum-Trading.md",
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
    relativePath: "08-AI閻儴鐦戞惔?10-raw/books/21st-Century-Monetary-Policy.md",
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
    relativePath: "08-AI閻儴鐦戞惔?20-wiki/concepts/Wyckoff-methodology.md",
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
    title: "Karpathy LLM Wiki workflow note",
    relativePath: "08-AI知识库/20-wiki/sources/Karpathy-LLM-Wiki-workflow-note.md",
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
    relativePath: "08-AI閻儴鐦戞惔?20-wiki/concepts/Using-ChatGPT-as-a-support-tool-for-investing-workflows.md",
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
      path.join(config.vaultPath, config.machineRoot, "10-raw", "manual", "2026-04-08-Codex-batch-smoke-A.md"),
      "# Batch Smoke\n",
      "utf8"
    );
    fs.writeFileSync(
      path.join(config.vaultPath, config.machineRoot, "10-raw", "manual", "2026-04-08-鍘嗗彶-Codex-绾跨▼瀵煎叆-渚嬪瓙.md"),
      "# Historical Thread Import\n",
      "utf8"
    );
    fs.writeFileSync(
      path.join(config.vaultPath, config.machineRoot, "10-raw", "manual", "2026-04-07-浜ゆ槗鍘熻瘽涓庡甯堝鐩橀€愭潯瀵圭収.md"),
      "# Duplicate Reference Case Candidate\n",
      "utf8"
    );

    fs.mkdirSync(
      path.join(config.vaultPath, config.machineRoot, "99-archive", "encoding-quarantine"),
      { recursive: true }
    );
    fs.mkdirSync(
      path.join(config.vaultPath, config.machineRoot, "99-archive", "validation-false-positives"),
      { recursive: true }
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

    const batchReviewDir = path.join(tempRoot, ".tmp-codex-thread-handoff-batch");
    const batchBodiesDir = path.join(batchReviewDir, "bodies");
    fs.mkdirSync(batchBodiesDir, { recursive: true });
    fs.writeFileSync(
      path.join(batchBodiesDir, "2026-04-05-trading-case.md"),
      `## User Request

This is a FOMO chase review.

## Assistant Response

This body is ready for import.`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(batchBodiesDir, "2026-04-05-pending-draft.md"),
      `## User Request

[Paste the user request or prompt summary here]

## Assistant Response

[Paste the final assistant answer here]
`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(batchReviewDir, "manifest.json"),
      JSON.stringify(
        {
          defaults: {
            source_label: "Codex batch import",
            compile: true,
            status: "queued"
          },
          entries: [
            {
              thread_uri: "codex://threads/trading-review",
              topic: "trading psychology",
              title: "2026-04-05 trading review candidate",
              body_file: "bodies/2026-04-05-trading-case.md",
              reference_case_candidate: "likely",
              candidate_tags: ["trading-psychology-reference-case"],
              review_hint:
                "Likely trading psychology / trade review material. After capture, review whether it should promote into 03-Reference Cases."
            },
            {
              thread_uri: "codex://threads/trading-draft",
              topic: "trading psychology",
              title: "2026-04-05 pending trading review",
              body_file: "bodies/2026-04-05-pending-draft.md",
              reference_case_candidate: "likely",
              candidate_tags: ["trading-psychology-reference-case"],
              review_hint:
                "Likely trading psychology / trade review material, but the body template still needs to be filled."
            }
          ]
        },
        null,
        2
      ),
      "utf8"
    );
    const reviewManifestPath = path.join(batchReviewDir, "manifest.json");
    const pendingDraftPath = path.join(batchBodiesDir, "2026-04-05-pending-draft.md");
    const reviewTimestamp = new Date("2026-04-05T08:58:00+08:00");
    fs.utimesSync(reviewManifestPath, reviewTimestamp, reviewTimestamp);
    fs.utimesSync(pendingDraftPath, reviewTimestamp, reviewTimestamp);

    const results = refreshWikiViews(config, {
      allowFilesystemFallback: true,
      preferCli: false,
      timestamp: "2026-04-05T09:00:00+08:00"
    });

    assert.equal(results.length, 20);

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
    const staleNotesContent = fs.readFileSync(
      path.join(config.vaultPath, getStaleNotesPath(config.machineRoot)),
      "utf8"
    );
    const openQuestionsContent = fs.readFileSync(
      path.join(config.vaultPath, getOpenQuestionsPath(config.machineRoot)),
      "utf8"
    );
    const sourcesByTopicContent = fs.readFileSync(
      path.join(config.vaultPath, getSourcesByTopicPath(config.machineRoot)),
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
    const codexThreadBatchReviewQueueContent = fs.readFileSync(
      path.join(config.vaultPath, getCodexThreadBatchReviewQueuePath(config.machineRoot)),
      "utf8"
    );
    const codexThreadBodyDraftQueueContent = fs.readFileSync(
      path.join(config.vaultPath, getCodexThreadBodyDraftQueuePath(config.machineRoot)),
      "utf8"
    );
    const kbCleanupReviewContent = fs.readFileSync(
      path.join(config.vaultPath, getKbCleanupReviewPath(config.machineRoot)),
      "utf8"
    );
    const kbCleanupProposedMovesContent = fs.readFileSync(
      path.join(config.vaultPath, getKbCleanupProposedMovesPath(config.machineRoot)),
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
    assert.match(dashboardContent, /Codex Thread Batch Review Queue/);
    assert.match(dashboardContent, /Codex Thread Body Draft Queue/);
    assert.match(dashboardContent, /KB Cleanup Review/);
    assert.match(dashboardContent, /KB Cleanup Proposed Moves/);
    assert.match(staleNotesContent, /Generated at: 2026-04-05T09:00:00\+08:00/);
    assert.match(staleNotesContent, /Stale Raw \(Queued > 14 days\)/);
    assert.match(openQuestionsContent, /Generated at: 2026-04-05T09:00:00\+08:00/);
    assert.match(openQuestionsContent, /draft wiki notes:/);
    assert.match(sourcesByTopicContent, /Generated at: 2026-04-05T09:00:00\+08:00/);
    assert.match(sourcesByTopicContent, /Wiki Coverage by Topic/);
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
    assert.match(codexThreadStatusContent, /likely batch review candidates: 2/);
    assert.match(codexThreadStatusContent, /ready candidate bodies: 1/);
    assert.match(codexThreadStatusContent, /template-pending candidate bodies: 1/);
    assert.match(codexThreadStatusContent, /missing candidate bodies: 0/);
    assert.match(codexThreadStatusContent, /Codex-Thread-Note/);
    assert.match(codexThreadStatusContent, /thread-a/);
    assert.match(codexThreadStatusContent, /Codex-Thread-Concept/);
    assert.match(codexThreadStatusContent, /Recent Verify Runs/);
    assert.match(codexThreadStatusContent, /Recent Reconcile Runs/);
    assert.match(codexThreadStatusContent, /Latest Missing Threads/);
    assert.match(codexThreadStatusContent, /Latest Recovery Package/);
    assert.match(codexThreadStatusContent, /Related Views/);
    assert.match(codexThreadStatusContent, /Codex Thread Batch Review Queue/);
    assert.match(codexThreadStatusContent, /Codex Thread Body Draft Queue/);
    assert.match(codexThreadStatusContent, /Batch Review Queue Snapshot/);
    assert.match(codexThreadStatusContent, /Priority/);
    assert.match(codexThreadStatusContent, /Why First/);
    assert.match(codexThreadStatusContent, /Estimated Effort/);
    assert.match(codexThreadStatusContent, /Ready to Capture/);
    assert.match(codexThreadStatusContent, /Needs Body First/);
    assert.match(codexThreadStatusContent, /Repair Body Path/);
    assert.match(codexThreadStatusContent, /2026-04-05 trading review candidate/);
    assert.match(codexThreadStatusContent, /2026-04-05 pending trading review/);
    assert.match(codexThreadStatusContent, /trading-review/);
    assert.match(codexThreadStatusContent, /trading-draft/);
    assert.match(codexThreadStatusContent, /run batch capture/);
    assert.match(codexThreadStatusContent, /fill body first/);
    assert.match(codexThreadStatusContent, /P0|P1/);
    assert.match(codexThreadStatusContent, /today \+ blocked by missing body|today \+ ready to import/);
    assert.match(codexThreadStatusContent, /1-2 min|5-10 min/);
    assert.match(codexThreadStatusContent, /Target File/);
    assert.match(codexThreadStatusContent, /Command Hint/);
    assert.match(codexThreadStatusContent, /Safe Hint/);
    assert.match(codexThreadStatusContent, /capture-codex-thread-batch\.mjs --manifest/);
    assert.match(codexThreadStatusContent, /skip-reference-refresh/);
    assert.match(codexThreadStatusContent, /\.tmp-codex-thread-handoff-batch\/bodies\/2026-04-05-tradin/);
    assert.match(codexThreadStatusContent, /file:\/\/\//);
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
    assert.match(codexThreadBatchReviewQueueContent, /Codex Thread Batch Review Queue/);
    assert.match(codexThreadBatchReviewQueueContent, /likely trading reference candidates: 2/i);
    assert.match(codexThreadBatchReviewQueueContent, /ready-to-capture: 1/i);
    assert.match(codexThreadBatchReviewQueueContent, /fill-body-first: 1/i);
    assert.match(codexThreadBatchReviewQueueContent, /repair-body-path: 0/i);
    assert.match(codexThreadBatchReviewQueueContent, /today priority candidates: 1/i);
    assert.match(codexThreadBatchReviewQueueContent, /quick wins \(<=3 min\): 1/i);
    assert.match(codexThreadBatchReviewQueueContent, /shared manifest groups: 1/i);
    assert.match(codexThreadBatchReviewQueueContent, /high-leverage groups: 0/i);
    assert.match(codexThreadBatchReviewQueueContent, /medium-leverage groups: 1/i);
    assert.match(codexThreadBatchReviewQueueContent, /low-leverage groups: 0/i);
    assert.match(codexThreadBatchReviewQueueContent, /2026-04-05 trading review candidate/);
    assert.match(codexThreadBatchReviewQueueContent, /2026-04-05 pending trading review/);
    assert.match(codexThreadBatchReviewQueueContent, /trading-review/);
    assert.match(codexThreadBatchReviewQueueContent, /trading-draft/);
    assert.match(codexThreadBatchReviewQueueContent, /trading-psychology-reference-case/);
    assert.match(codexThreadBatchReviewQueueContent, /ready/);
    assert.match(codexThreadBatchReviewQueueContent, /Ready to Capture/);
    assert.match(codexThreadBatchReviewQueueContent, /Needs Body First/);
    assert.match(codexThreadBatchReviewQueueContent, /Repair Body Path/);
    assert.match(codexThreadBatchReviewQueueContent, /Today Priority Queue/);
    assert.match(codexThreadBatchReviewQueueContent, /Quick Wins/);
    assert.match(codexThreadBatchReviewQueueContent, /Shared Manifest Groups/);
    assert.match(codexThreadBatchReviewQueueContent, /Batch ROI/);
    assert.match(codexThreadBatchReviewQueueContent, /Ready After Fill/);
    assert.match(codexThreadBatchReviewQueueContent, /Release/);
    assert.match(codexThreadBatchReviewQueueContent, /Suggested Actions/);
    assert.match(codexThreadBatchReviewQueueContent, /run batch capture/);
    assert.match(codexThreadBatchReviewQueueContent, /fill body first/);
    assert.match(codexThreadBatchReviewQueueContent, /Priority/);
    assert.match(codexThreadBatchReviewQueueContent, /Why First/);
    assert.match(codexThreadBatchReviewQueueContent, /Estimated Effort/);
    assert.match(codexThreadBatchReviewQueueContent, /P0|P1/);
    assert.match(codexThreadBatchReviewQueueContent, /today \+ blocked by missing body|today \+ ready to import/);
    assert.match(codexThreadBatchReviewQueueContent, /1-2 min|5-10 min/);
    assert.match(codexThreadBatchReviewQueueContent, /Medium leverage/);
    assert.match(codexThreadBatchReviewQueueContent, /\+1 after fill/);
    assert.match(codexThreadBatchReviewQueueContent, /Target File/);
    assert.match(codexThreadBatchReviewQueueContent, /Command Hint/);
    assert.match(codexThreadBatchReviewQueueContent, /Safe Hint/);
    assert.match(codexThreadBatchReviewQueueContent, /capture-codex-thread-batch\.mjs --manifest/);
    assert.match(codexThreadBatchReviewQueueContent, /skip-reference-refresh/);
    assert.match(codexThreadBatchReviewQueueContent, /shared manifest/i);
    assert.match(codexThreadBatchReviewQueueContent, /fill the remaining body drafts first, then import together/i);
    assert.match(codexThreadBatchReviewQueueContent, /\.tmp-codex-thread-handoff-batch\/bodies\/2026-04-05-trading-case\.md/);
    assert.match(codexThreadBatchReviewQueueContent, /\.tmp-codex-thread-handoff-batch\/bodies\/2026-04-05-pending-draft\.md/);
    assert.match(codexThreadBatchReviewQueueContent, /file:/);
    assert.match(codexThreadBatchReviewQueueContent, /file:\/\/\//);
    assert.match(codexThreadBodyDraftQueueContent, /Codex Thread Body Draft Queue/);
    assert.match(codexThreadBodyDraftQueueContent, /pending body drafts: 1/i);
    assert.match(codexThreadBodyDraftQueueContent, /today new drafts: 1/i);
    assert.match(codexThreadBodyDraftQueueContent, /quick fill candidates \(<=10 min\): 1/i);
    assert.match(codexThreadBodyDraftQueueContent, /Highest Priority Drafts/);
    assert.match(codexThreadBodyDraftQueueContent, /Quick Fill Candidates/);
    assert.match(codexThreadBodyDraftQueueContent, /Today New Drafts/);
    assert.match(codexThreadBodyDraftQueueContent, /Fill These First/);
    assert.match(codexThreadBodyDraftQueueContent, /Priority/);
    assert.match(codexThreadBodyDraftQueueContent, /Why First/);
    assert.match(codexThreadBodyDraftQueueContent, /Estimated Effort/);
    assert.match(codexThreadBodyDraftQueueContent, /Ready After Fill/);
    assert.match(codexThreadBodyDraftQueueContent, /2026-04-05 pending trading review/);
    assert.match(codexThreadBodyDraftQueueContent, /trading-draft/);
    assert.match(codexThreadBodyDraftQueueContent, /Updated/);
    assert.match(codexThreadBodyDraftQueueContent, /2026-04-05T08:58:00\+08:00/);
    assert.match(codexThreadBodyDraftQueueContent, /P0/);
    assert.match(codexThreadBodyDraftQueueContent, /today \+ blocked by missing body/);
    assert.match(codexThreadBodyDraftQueueContent, /5-10 min/);
    assert.match(codexThreadBodyDraftQueueContent, /\+1 ready after fill/);
    assert.match(codexThreadBodyDraftQueueContent, /\.tmp-codex-thread-handoff-batch\/bodies\/2026-04-05-pending-draft\.md/);
    assert.match(codexThreadBodyDraftQueueContent, /fill ".*2026-04-05-pending-draft\.md"/);
    assert.match(codexThreadBodyDraftQueueContent, /fill "/);
    assert.match(kbCleanupReviewContent, /KB Cleanup Review/);
    assert.match(kbCleanupReviewContent, /This page is review-only/);
    assert.match(kbCleanupReviewContent, /batch_smoke/);
    assert.match(kbCleanupReviewContent, /thread_import/);
    assert.match(kbCleanupReviewContent, /raw_reference_case_duplicates/);
    assert.match(kbCleanupReviewContent, /encoding-quarantine/);
    assert.match(kbCleanupReviewContent, /validation-false-positives/);
    assert.match(kbCleanupReviewContent, /Review 1 batch smoke note/);
    assert.match(kbCleanupProposedMovesContent, /KB Cleanup Proposed Moves/);
    assert.match(kbCleanupProposedMovesContent, /review for archive/);
    assert.match(kbCleanupProposedMovesContent, /manual-smoke/);
    assert.match(kbCleanupProposedMovesContent, /manual-smoke/);
    assert.match(kbCleanupProposedMovesContent, /review-only/);
    assert.match(kbCleanupProposedMovesContent, /These are suggestions only|Dry Run Plan/);
    assert.match(kbCleanupProposedMovesContent, /These are suggestions only/);
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

run("draft trading plan parser recognizes style, delivery target, and synthesis mode", () => {
  const parsed = parseDraftTradingPlanArgs([
    "--plan-file",
    "plans/current-plan.md",
    "--style",
    "Dalio",
    "--deliver-to",
    "研究搭档",
    "--execute",
    "--write-synthesis"
  ]);

  assert.equal(parsed.planFile, "plans/current-plan.md");
  assert.equal(parsed.style, "dalio");
  assert.equal(parsed.deliverTo, "研究搭档");
  assert.equal(parsed.execute, true);
  assert.equal(parsed.writeSynthesis, true);
});

run("draft trading plan style normalizer maps aliases to canonical keys", () => {
  assert.equal(normalizeTradingPlanStyle("Marks"), "howard-marks");
  assert.equal(normalizeTradingPlanStyle("workbench"), "roundtable");
  assert.equal(normalizeTradingPlanStyle("unknown-style"), "roundtable");
});

run("draft trading plan retrieval query anchors workbench and style terms", () => {
  const query = buildTradingPlanRetrievalQuery(
    "中国西电 观察仓，等放量突破再加，失效点是前低跌破。",
    "druckenmiller"
  );

  assert.match(query, /Legendary investor workbench v3/i);
  assert.match(query, /Druckenmiller/i);
  assert.match(query, /中国西电/);
});

run("draft trading plan prompt injects plan input and delivery target", () => {
  const prompt = buildTradingPlanPrompt(
    "STYLE={{STYLE_GUIDE}}\nTO={{DELIVER_TO}}\nPLAN={{PLAN_INPUT}}\nQUERY={{QUERY}}\nTOPIC={{TOPIC}}\nNOTES={{NOTE_CONTEXT}}",
    {
      styleGuide: "Be strict.",
      deliverTo: "投委会",
      planInput: "计划：突破后再加仓。",
      query: "Legendary investor workbench v3 trading plan",
      topic: "legendary investor",
      noteContext: "### Note 1: Demo"
    }
  );

  assert.match(prompt, /Be strict\./);
  assert.match(prompt, /投委会/);
  assert.match(prompt, /突破后再加仓/);
  assert.match(prompt, /### Note 1: Demo/);
});

run("legendary workbench parser keeps goal and synthesis flags", () => {
  const parsed = parseLegendaryWorkbenchArgs([
    "--plan-file",
    "plans/current-plan.md",
    "--session-goal",
    "完整跑五段流程",
    "--execute",
    "--write-synthesis"
  ]);

  assert.equal(parsed.planFile, "plans/current-plan.md");
  assert.equal(parsed.sessionGoal, "完整跑五段流程");
  assert.equal(parsed.execute, true);
  assert.equal(parsed.writeSynthesis, true);
});

run("legendary workbench parser keeps json export flags", () => {
  const parsed = parseLegendaryWorkbenchArgs([
    "--plan-file",
    "plans/current-plan.md",
    "--execute",
    "--write-json",
    "--json-file",
    "handoff/custom-legendary.json"
  ]);

  assert.equal(parsed.execute, true);
  assert.equal(parsed.writeJson, true);
  assert.equal(parsed.jsonFile, "handoff/custom-legendary.json");
});

run("legendary workbench query anchors staged mentor workflow", () => {
  const query = buildLegendaryWorkbenchQuery(
    "中国海油主腿，山东黄金对冲，招商南油确认后做。"
  );

  assert.match(query, /Legendary investor workbench v3/i);
  assert.match(query, /critic/i);
  assert.match(query, /roundtable/i);
  assert.match(query, /中国海油/);
});

run("legendary workbench prompt injects plan and session goal", () => {
  const prompt = buildLegendaryWorkbenchPrompt(
    "PLAN={{PLAN_INPUT}}\nGOAL={{SESSION_GOAL}}\nNOTES={{NOTE_CONTEXT}}",
    {
      planInput: "计划：先中国海油，后山东黄金。",
      sessionGoal: "完整跑五段流程",
      noteContext: "### Note 1: Legendary-Investor-Workbench-v3"
    }
  );

  assert.match(prompt, /先中国海油/);
  assert.match(prompt, /完整跑五段流程/);
  assert.match(prompt, /Legendary-Investor-Workbench-v3/);
});

run("legendary workbench collects required mentor notes by title", () => {
  const notes = collectRequiredNotes([
    {
      title: "Legendary-Investor-Workbench-v3",
      relativePath: "08-AI知识库/20-wiki/syntheses/Legendary-Investor-Workbench-v3.md"
    },
    {
      title: "Druckenmiller-Critic-Card",
      relativePath: "08-AI知识库/20-wiki/syntheses/Druckenmiller-Critic-Card.md"
    },
    {
      title: "Prompt-Template---单导师模式",
      relativePath: "08-AI知识库/20-wiki/syntheses/Prompt-Template---单导师模式.md"
    }
  ]);

  assert.equal(notes.length, 3);
  assert.equal(notes[0].title, "Legendary-Investor-Workbench-v3");
});

run("legendary workbench local fallback leg parsing keeps chinese trade roles readable", () => {
  const prompt = buildLegendaryWorkbenchPrompt(
    "PLAN={{PLAN_INPUT}}\nGOAL={{SESSION_GOAL}}\nSTAGE={{STAGE_TITLE}}\nINS={{STAGE_INSTRUCTIONS}}\nPRIOR={{PRIOR_CONTEXT}}\nNOTES={{NOTE_CONTEXT}}",
    {
      planInput: "中国海油主腿，山东黄金对冲，招商南油确认后做。",
      sessionGoal: "完整跑五段流程",
      stageTitle: "Workbench v3",
      stageInstructions: "Classify the situation.",
      priorContext: "(none yet)",
      noteContext: "Legendary investor notes"
    }
  );

  assert.match(prompt, /中国海油主腿/);
  assert.match(prompt, /招商南油确认后做/);
});

run("legendary workbench analyzer extracts the three trade legs from the real plan style", () => {
  const summary = analyzeTradingPlan(`
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

第一优先是 中国海油
第二优先才是 招商南油
对冲优先是 山东黄金

主做 中国海油
弹性选 招商南油
如果担心消息反转，就加 山东黄金
`);

  assert.equal(summary.primaryLeg, "中国海油");
  assert.equal(summary.hedgeLeg, "山东黄金");
  assert.equal(summary.confirmLeg, "招商南油");
});

run("legendary reasoner stage fallback embeds mentor logic and parsed trade cards", () => {
  const output = buildLegendaryStageFallback(
    { key: "single_mentor", title: "单导师" },
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`,
    [],
    []
  );

  assert.match(output, /Druckenmiller/);
  assert.match(output, /中国海油/);
  assert.match(output, /放量过 5\.00/);
  assert.match(output, /不要把“脑补升级”误当成“事实升级”/);
});

run("legendary reasoner roundtable committee returns structured mentor vote cards", () => {
  const summary = analyzeTradingPlan(`
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
不是彻底破裂
担心消息反转
油运最容易被冲高回落误伤

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`);

  const committee = buildRoundtableCommittee(summary);

  assert.equal(committee.cards.length, 3);
  assert.deepEqual(
    committee.cards.map((card) => [card.mentor, card.vote]),
    [
      ["Druckenmiller", "support"],
      ["Howard Marks", "support"],
      ["Dalio", "conditional"]
    ]
  );
  assert.match(committee.committeeMaxPosition, /中国海油 0\.40/);
  assert.match(committee.committeeMaxPosition, /山东黄金 0\.25/);
  assert.match(committee.committeeMaxPosition, /招商南油 0\.15/);
  assert.match(committee.verdict.defaultStructure, /中国海油 0\.40 \+ 山东黄金 0\.25/);
  assert.match(committee.verdict.upgradePath, /招商南油 只有在 放量过 5\.00 后/);
  assert.match(committee.verdict.downgradeSequence, /先减 招商南油/);
  assert.deepEqual(committee.verdict.priorityOrder, ["中国海油", "山东黄金", "招商南油"]);
  assert.match(committee.cards[0].keyEvidence, /催化映射/);
  assert.match(committee.cards[1].killSwitch, /优先保留对冲/);
});

run("legendary reasoner roundtable stage fallback renders committee vote cards", () => {
  const output = buildLegendaryStageFallback(
    { key: "roundtable", title: "圆桌讨论" },
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
不是彻底破裂
担心消息反转

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`,
    [],
    []
  );

  assert.match(output, /\| Mentor \| Vote \| Confidence \| Max Position \|/);
  assert.match(output, /\| Druckenmiller \| 支持 \|/);
  assert.match(output, /\| Howard Marks \| 支持 \|/);
  assert.match(output, /\| Dalio \| 有条件支持 \|/);
  assert.match(output, /委员会组合上限：/);
  assert.match(output, /默认结构：/);
  assert.match(output, /升级路径：/);
  assert.match(output, /降级顺序：/);
  assert.match(output, /禁止动作：/);
  assert.match(output, /Druckenmiller key evidence:/);
  assert.match(output, /Howard Marks kill switch:/);
});

run("legendary reasoner final action card consumes committee verdict", () => {
  const output = buildLegendaryStageFallback(
    { key: "final_action_card", title: "Final Action Card" },
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
不是彻底破裂
担心消息反转

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`,
    [],
    []
  );

  assert.match(output, /默认结构：中国海油 0\.40 \+ 山东黄金 0\.25，招商南油 默认后置/);
  assert.match(output, /升级路径：招商南油 只有在 放量过 5\.00 后/);
  assert.match(output, /降级顺序：先减 招商南油/);
});

run("legendary doctrines render mentor-specific templates", () => {
  const doctrine = getLegendaryDoctrine("Druckenmiller");
  assert.equal(doctrine.name, "Druckenmiller");

  const line = renderDoctrineLine("Howard Marks", "actionCardNote", {
    primaryLeg: "中国海油"
  });
  assert.match(line, /Howard Marks/);
  assert.match(line, /风险预算/);
});

run("legendary reasoner switches single mentor to Buffett for valuation-style prompts", () => {
  const summary = analyzeTradingPlan("这家公司护城河深、现金流强、资本配置优秀，值得未来五年持有吗？");
  assert.equal(summary.singleMentor, "Buffett");
  assert.equal(summary.roundtablePlaybookKey, "valuation_quality");
  assert.deepEqual(summary.roundtableMentors, ["Buffett", "Howard Marks", "GMO"]);
  assert.equal(summary.primaryLeg, "核心标的");
  assert.equal(summary.hedgeLeg, "防守仓");
  assert.equal(summary.confirmLeg, "加仓位");
});

run("legendary reasoner routes price-hike plans into the supply-demand committee", () => {
  const summary = analyzeTradingPlan(`
电子布涨价周期交易计划

一句话结论：电子布供应紧缺，涨价在即。

主腿：中材科技
对冲腿：中国巨石
弹性腿：宏和科技

产业判断：
电子布供不应求，景气上行，稼动率维持高位，覆铜板产业链排产紧张。
`);

  assert.equal(summary.roundtablePlaybookKey, "supply_demand_cycle");
  assert.equal(summary.scenarioLabel, "供需周期交易工作台");
  assert.deepEqual(summary.roundtableMentors, ["Druckenmiller", "Howard Marks", "Buffett"]);
  assert.equal(summary.signals.priceHike, true);
  assert.equal(summary.signals.supplyShortage, true);
  assert.equal(summary.signals.highUtilization, true);
  assert.equal(summary.signals.electronicCloth, true);
});

run("legendary reasoner supply-demand committee gives Buffett support and stronger confidence", () => {
  const summary = analyzeTradingPlan(`
电子布涨价周期交易计划

一句话结论：电子布供应紧缺，涨价在即。

主腿：中材科技
对冲腿：中国巨石
弹性腿：宏和科技

产业判断：
电子布供不应求，景气上行，稼动率维持高位，覆铜板产业链排产紧张，公司具备定价权和提价能力。

标的\t主题入场\t确认入场\t失效
中材科技\t18.0-19.0\t过20.0放量\t跌破16.5
中国巨石\t15.0-16.0\t过17.0\t跌破14.0
宏和科技\t25.0-26.0\t放量过28.0\t跌破23.0
`);

  const committee = buildRoundtableCommittee(summary);
  const buffettCard = committee.cards.find((card) => card.mentor === "Buffett");

  assert.equal(summary.roundtablePlaybookKey, "supply_demand_cycle");
  assert.ok(buffettCard);
  assert.equal(buffettCard.vote, "support");
  assert.ok(buffettCard.confidence >= 70);
  assert.match(committee.verdict.doNotDo, /涨价预期/);
});

run("legendary workbench run report marks provider and local fallback stages", () => {
  const report = buildRunReport([
    { stage: { title: "Workbench v3" }, mode: "provider" },
    { stage: { title: "Critic Mode" }, mode: "local-fallback" }
  ]);

  assert.match(report, /\| Workbench v3 \| provider \|/);
  assert.match(report, /\| Critic Mode \| local-fallback \|/);
});

run("legendary workbench json export keeps committee verdict and stage outputs", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
不是彻底破裂

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`,
    [
      {
        stage: { key: "roundtable", title: "圆桌讨论" },
        mode: "local-fallback",
        output: "委员会票型：2 支持 / 1 有条件支持 / 0 反对。",
        notes: [{ title: "Legendary-Investor-Workbench-v3" }]
      }
    ],
    {
      sessionGoal: "完整跑五段流程",
      retrievalQuery: "Legendary investor workbench v3",
      selectedNotes: [
        {
          title: "Legendary-Investor-Workbench-v3",
          relativePath: "08-AI知识库/20-wiki/syntheses/Legendary-Investor-Workbench-v3.md"
        }
      ]
    }
  );

  assert.equal(exportData.schemaVersion, 1);
  assert.equal(exportData.summary.primaryLeg, "中国海油");
  assert.equal(exportData.playbook.key, "event_driven_risk");
  assert.equal(exportData.committee.voteCards.length, 3);
  assert.match(exportData.committee.verdict.defaultStructure, /中国海油 0\.40 \+ 山东黄金 0\.25/);
  assert.equal(exportData.tradeCards.confirm.confirmEntry, "放量过 5.00");
  assert.equal(exportData.stages[0].key, "roundtable");
  assert.equal(exportData.selectedNotes[0].title, "Legendary-Investor-Workbench-v3");
});

run("legendary workbench json export path defaults into handoff", () => {
  const filePath = resolveLegendaryWorkbenchJsonPath(
    { jsonFile: "" },
    { projectRoot: "C:/workspace/obsidian-kb-local" },
    "plan"
  );

  assert.equal(
    filePath,
    "C:\\workspace\\obsidian-kb-local\\handoff\\legendary-investor-last-run.json"
  );
});

run("legendary investor checklist parser keeps json flags", () => {
  const parsed = parseLegendaryInvestorChecklistArgs([
    "--json",
    "--json-file",
    "handoff/custom-run.json"
  ]);

  assert.equal(parsed.json, true);
  assert.equal(parsed.jsonFile, "handoff/custom-run.json");
});

run("legendary investor checklist parser keeps state mutation flags", () => {
  const parsed = parseLegendaryInvestorChecklistArgs([
    "--state-file",
    "handoff/checklist-state.json",
    "--check",
    "event_status,primary_leg",
    "--uncheck",
    "hedge_leg",
    "--note",
    "primary_leg=主腿已核验",
    "--reset-state"
  ]);

  assert.equal(parsed.stateFile, "handoff/checklist-state.json");
  assert.deepEqual(parsed.checkIds, ["event_status", "primary_leg"]);
  assert.deepEqual(parsed.uncheckIds, ["hedge_leg"]);
  assert.equal(parsed.notes.primary_leg, "主腿已核验");
  assert.equal(parsed.resetState, true);
});

run("legendary investor checklist path defaults into handoff", () => {
  const filePath = resolveLegendaryInvestorChecklistSourcePath(
    { jsonFile: "" },
    { projectRoot: "C:/workspace/obsidian-kb-local" }
  );

  assert.equal(
    filePath,
    "C:\\workspace\\obsidian-kb-local\\handoff\\legendary-investor-last-run.json"
  );
});

run("legendary investor checklist state path defaults into handoff", () => {
  const filePath = resolveLegendaryInvestorChecklistStatePath(
    { stateFile: "" },
    { projectRoot: "C:/workspace/obsidian-kb-local" }
  );

  assert.equal(
    filePath,
    "C:\\workspace\\obsidian-kb-local\\handoff\\legendary-investor-checklist-state.json"
  );
});

run("legendary investor checklist builds event-driven preopen checks from exported run", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`,
    []
  );

  const checklist = buildLegendaryInvestorChecklist(exportData, {
    generatedAt: "2026-04-12T00:00:00.000Z"
  });
  const rendered = renderLegendaryInvestorChecklist(checklist, {
    sourcePath: "handoff/legendary-investor-last-run.json"
  });

  assert.equal(checklist.playbook.key, "event_driven_risk");
  assert.equal(checklist.checklist[0].category, "preopen");
  assert.match(rendered, /核验事件没有出现实质性缓和或协议突破/);
  assert.match(rendered, /中国海油: 主题入场 38\.0-38\.8 \/ 确认 39\.5 上方站稳 \/ 失效 跌破 36\.5/);
});

run("legendary investor checklist applies persisted check state and notes", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
    []
  );
  const report = buildLegendaryInvestorChecklist(exportData, {
    state: {
      schemaVersion: 1,
      items: {
        event_status: {
          checked: true,
          checkedAt: "2026-04-12T00:00:00.000Z",
          note: "消息面已核验"
        }
      }
    }
  });
  const rendered = renderLegendaryInvestorChecklist(report);

  assert.equal(report.checklist.find((item) => item.id === "event_status").checked, true);
  assert.match(rendered, /\[x\] 核验事件没有出现实质性缓和或协议突破/);
  assert.match(rendered, /note: 消息面已核验/);
  assert.match(rendered, /checked_at: 2026-04-12T00:00:00.000Z/);
});

run("legendary investor checklist keeps valuation playbook language clean", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    "如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？",
    []
  );
  const checklist = buildLegendaryInvestorChecklist(exportData, {
    generatedAt: "2026-04-12T00:00:00.000Z"
  });
  const rendered = renderLegendaryInvestorChecklist(checklist);

  assert.equal(checklist.playbook.key, "valuation_quality");
  assert.match(rendered, /核验企业质量是否仍然成立/);
  assert.match(rendered, /核验当前价格是否仍有赔率/);
  assert.doesNotMatch(rendered, /无协议/);
  assert.doesNotMatch(rendered, /headline/);
});

run("legendary investor checklist keeps supply-demand playbook language clean", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
电子布涨价周期交易计划

一句话结论：电子布供应紧缺，涨价在即。

主腿：中材科技
对冲腿：中国巨石
弹性腿：宏和科技

产业判断：
电子布供不应求，景气上行，稼动率维持高位，覆铜板产业链排产紧张，公司具备定价权和提价能力。
`,
    []
  );
  const checklist = buildLegendaryInvestorChecklist(exportData, {
    generatedAt: "2026-04-13T00:00:00.000Z"
  });
  const rendered = renderLegendaryInvestorChecklist(checklist);

  assert.equal(checklist.playbook.key, "supply_demand_cycle");
  assert.match(rendered, /核验涨价\/提价是否仍在兑现/);
  assert.match(rendered, /核验供给是否继续紧张/);
  assert.match(rendered, /核验景气\/稼动率是否仍维持高位/);
  assert.match(rendered, /核验 中材科技 仍是定价权最强主腿/);
  assert.match(rendered, /确认 宏和科技 只有在景气确认后才加仓/);
  assert.doesNotMatch(rendered, /无协议/);
  assert.doesNotMatch(rendered, /headline/);
});

run("legendary investor checklist runner prints json output", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-checklist-"));
  const jsonPath = path.join(tempRoot, "legendary-investor-last-run.json");
  fs.writeFileSync(
    jsonPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        "如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？",
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    const lines = [];
    const report = runLegendaryInvestorChecklist(["--json", "--json-file", jsonPath], {
      config: { projectRoot: tempRoot },
      writer: {
        log(value) {
          lines.push(String(value));
        }
      }
    });

    assert.equal(report.playbook.key, "valuation_quality");
    assert.match(lines[0], /"schemaVersion": 1/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor checklist runner persists state mutations", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-checklist-state-"));
  const jsonPath = path.join(tempRoot, "legendary-investor-last-run.json");
  const statePath = path.join(tempRoot, "legendary-investor-checklist-state.json");
  fs.writeFileSync(
    jsonPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    runLegendaryInvestorChecklist(
      [
        "--json-file",
        jsonPath,
        "--state-file",
        statePath,
        "--check",
        "event_status",
        "--note",
        "event_status=已完成核验"
      ],
      {
        config: { projectRoot: tempRoot },
        writer: { log() {} }
      }
    );

    const saved = loadLegendaryInvestorChecklistState(statePath);
    assert.equal(saved.items.event_status.checked, true);
    assert.equal(saved.items.event_status.note, "已完成核验");

    const lines = [];
    runLegendaryInvestorChecklist(
      ["--json-file", jsonPath, "--state-file", statePath],
      {
        config: { projectRoot: tempRoot },
        writer: {
          log(value) {
            lines.push(String(value));
          }
        }
      }
    );
    assert.match(lines[0], /\[x\] 核验事件没有出现实质性缓和或协议突破/);
    assert.match(lines[0], /note: 已完成核验/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor decision parser keeps fact args", () => {
  const parsed = parseLegendaryInvestorDecisionArgs([
    "--json",
    "--json-file",
    "handoff/custom-run.json",
    "--fact",
    "no_agreement=true",
    "--fact",
    "primary_leg_confirmed=1"
  ]);

  assert.equal(parsed.json, true);
  assert.equal(parsed.jsonFile, "handoff/custom-run.json");
  assert.equal(parsed.facts.no_agreement, "true");
  assert.equal(parsed.facts.primary_leg_confirmed, "1");
});

run("legendary investor decision parser keeps write-synthesis flags", () => {
  const parsed = parseLegendaryInvestorDecisionArgs([
    "--fact",
    "no_agreement=true",
    "--write-json",
    "--output-json-file",
    "handoff/decision.json",
    "--write-synthesis",
    "--skip-links",
    "--skip-views"
  ]);

  assert.equal(parsed.writeJson, true);
  assert.equal(parsed.outputJsonFile, "handoff/decision.json");
  assert.equal(parsed.writeSynthesis, true);
  assert.equal(parsed.skipLinks, true);
  assert.equal(parsed.skipViews, true);
});

run("legendary investor decision path defaults into handoff", () => {
  const filePath = resolveLegendaryInvestorDecisionSourcePath(
    { jsonFile: "" },
    { projectRoot: "C:/workspace/obsidian-kb-local" }
  );

  assert.equal(
    filePath,
    "C:\\workspace\\obsidian-kb-local\\handoff\\legendary-investor-last-run.json"
  );
});

run("legendary investor decision output path defaults into handoff", () => {
  const filePath = resolveLegendaryInvestorDecisionOutputPath(
    { outputJsonFile: "" },
    { projectRoot: "C:/workspace/obsidian-kb-local" }
  );

  assert.equal(
    filePath,
    "C:\\workspace\\obsidian-kb-local\\handoff\\legendary-investor-last-decision.json"
  );
});

run("legendary investor decision merges facts file and inline facts", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-decision-facts-"));
  const factsPath = path.join(tempRoot, "facts.json");
  fs.writeFileSync(
    factsPath,
    `${JSON.stringify({ no_agreement: true, risk_unresolved: true }, null, 2)}\n`,
    "utf8"
  );

  try {
    const facts = loadLegendaryDecisionFacts({
      factsFile: factsPath,
      facts: {
        primary_leg_confirmed: "1"
      }
    });

    assert.equal(facts.no_agreement, true);
    assert.equal(facts.risk_unresolved, true);
    assert.equal(facts.primary_leg_confirmed, "1");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor decision gives GO for event-driven default structure", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`,
    []
  );
  const report = buildLegendaryInvestorDecision(exportData, {
    no_agreement: true,
    risk_unresolved: true,
    primary_leg_confirmed: true,
    hedge_leg_confirmed: true,
    substantive_progress: false
  });
  const rendered = renderLegendaryInvestorDecision(report);

  assert.equal(report.verdict, "GO");
  assert.match(report.recommendedStructure, /中国海油 0\.40 \+ 山东黄金 0\.25/);
  assert.match(rendered, /Verdict: GO/);
});

run("legendary investor decision upgrades to full structure when confirm leg is confirmed", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破

标的\t主题入场\t确认入场\t失效
中国海油\t38.0-38.8\t39.5 上方站稳\t跌破 36.5
招商南油\t4.75-4.90\t放量过 5.00\t跌破 4.50
山东黄金\t40.0-41.0\t过 42.0\t跌破 38.8
`,
    []
  );
  const report = buildLegendaryInvestorDecision(exportData, {
    no_agreement: true,
    risk_unresolved: true,
    primary_leg_confirmed: true,
    confirm_leg_confirmed: true,
    substantive_progress: false
  });

  assert.equal(report.verdict, "GO");
  assert.match(report.recommendedStructure, /中国海油 -> 山东黄金 -> 招商南油/);
});

run("legendary investor decision gives WATCH when valuation odds are not attractive", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    "如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？",
    []
  );
  const report = buildLegendaryInvestorDecision(exportData, {
    quality_ok: true,
    odds_ok: false,
    hold_without_story: true
  });

  assert.equal(report.verdict, "WATCH");
  assert.match(report.nextStep, /不要因为喜欢企业就忽略价格/);
});

run("legendary investor decision gives GO for supply-demand default structure", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
电子布涨价周期交易计划

一句话结论：电子布供应紧缺，涨价在即。

主腿：中材科技
对冲腿：中国巨石
弹性腿：宏和科技

产业判断：
电子布供不应求，景气上行，稼动率维持高位，覆铜板产业链排产紧张，公司具备定价权和提价能力。

标的\t主题入场\t确认入场\t失效
中材科技\t18.0-19.0\t过20.0放量\t跌破16.5
中国巨石\t15.0-16.0\t过17.0\t跌破14.0
宏和科技\t25.0-26.0\t放量过28.0\t跌破23.0
`,
    []
  );
  const report = buildLegendaryInvestorDecision(exportData, {
    price_hike_confirmed: true,
    supply_shortage_confirmed: true,
    high_utilization_confirmed: true,
    primary_leg_confirmed: true,
    hedge_leg_confirmed: true
  });

  assert.equal(report.playbook.key, "supply_demand_cycle");
  assert.equal(report.verdict, "GO");
  assert.match(report.recommendedStructure, /中材科技 0\.35 \+ 中国巨石 0\.10/);
  assert.match(report.nextStep, /宏和科技 继续等待景气确认/);
});

run("legendary investor decision runner prints json output", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-decision-runner-"));
  const jsonPath = path.join(tempRoot, "legendary-investor-last-run.json");
  fs.writeFileSync(
    jsonPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    const lines = [];
    const report = runLegendaryInvestorDecision(
      [
        "--json",
        "--json-file",
        jsonPath,
        "--fact",
        "no_agreement=true",
        "--fact",
        "risk_unresolved=true",
        "--fact",
        "primary_leg_confirmed=true"
      ],
      {
        config: { projectRoot: tempRoot },
        writer: {
          log(value) {
            lines.push(String(value));
          }
        }
      }
    );

    assert.equal(report.verdict, "GO");
    assert.match(lines[0], /"verdict": "GO"/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor decision can persist latest decision json", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-decision-json-"));
  const jsonPath = path.join(tempRoot, "decision.json");

  try {
    const written = writeLegendaryInvestorDecisionJson(jsonPath, {
      verdict: "GO"
    });
    assert.equal(written, jsonPath);
    assert.equal(JSON.parse(fs.readFileSync(jsonPath, "utf8")).verdict, "GO");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor review parser keeps fact args", () => {
  const parsed = parseLegendaryInvestorReviewArgs([
    "--json",
    "--json-file",
    "handoff/custom-run.json",
    "--fact",
    "traded_fact_not_story=true",
    "--fact",
    "chased_confirm_leg=false"
  ]);

  assert.equal(parsed.json, true);
  assert.equal(parsed.jsonFile, "handoff/custom-run.json");
  assert.equal(parsed.facts.traded_fact_not_story, "true");
  assert.equal(parsed.facts.chased_confirm_leg, "false");
});

run("legendary investor review parser keeps write-synthesis flags", () => {
  const parsed = parseLegendaryInvestorReviewArgs([
    "--fact",
    "traded_fact_not_story=true",
    "--write-json",
    "--output-json-file",
    "handoff/review.json",
    "--write-synthesis",
    "--skip-links",
    "--skip-views"
  ]);

  assert.equal(parsed.writeJson, true);
  assert.equal(parsed.outputJsonFile, "handoff/review.json");
  assert.equal(parsed.writeSynthesis, true);
  assert.equal(parsed.skipLinks, true);
  assert.equal(parsed.skipViews, true);
});

run("legendary investor review path defaults into handoff", () => {
  const filePath = resolveLegendaryInvestorReviewSourcePath(
    { jsonFile: "" },
    { projectRoot: "C:/workspace/obsidian-kb-local" }
  );

  assert.equal(
    filePath,
    "C:\\workspace\\obsidian-kb-local\\handoff\\legendary-investor-last-run.json"
  );
});

run("legendary investor review output path defaults into handoff", () => {
  const filePath = resolveLegendaryInvestorReviewOutputPath(
    { outputJsonFile: "" },
    { projectRoot: "C:/workspace/obsidian-kb-local" }
  );

  assert.equal(
    filePath,
    "C:\\workspace\\obsidian-kb-local\\handoff\\legendary-investor-last-review.json"
  );
});

run("legendary investor review merges facts file and inline facts", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-review-facts-"));
  const factsPath = path.join(tempRoot, "facts.json");
  fs.writeFileSync(
    factsPath,
    `${JSON.stringify({ traded_fact_not_story: true, primary_leg_was_stable: true }, null, 2)}\n`,
    "utf8"
  );

  try {
    const facts = loadLegendaryReviewFacts({
      factsFile: factsPath,
      facts: {
        hedge_leg_worked: "1"
      }
    });

    assert.equal(facts.traded_fact_not_story, true);
    assert.equal(facts.primary_leg_was_stable, true);
    assert.equal(facts.hedge_leg_worked, "1");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor review gives CLEAN for disciplined event-driven execution", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
    []
  );
  const report = buildLegendaryInvestorReview(exportData, {
    traded_fact_not_story: true,
    primary_leg_was_stable: true,
    hedge_leg_worked: true,
    confirm_leg_was_confirmed: true,
    chased_confirm_leg: false,
    respected_invalidation: true
  });
  const rendered = renderLegendaryInvestorReview(report);

  assert.equal(report.verdict, "CLEAN");
  assert.match(rendered, /Verdict: CLEAN/);
  assert.match(rendered, /结构、确认和风控基本一致/);
});

run("legendary investor review gives FAIL for valuation execution with price chasing", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    "如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？",
    []
  );
  const report = buildLegendaryInvestorReview(exportData, {
    quality_thesis_intact: true,
    odds_were_acceptable: false,
    hold_without_story: false,
    chased_price: true,
    added_without_new_evidence: true,
    respected_price_discipline: false
  });

  assert.equal(report.verdict, "FAIL");
  assert.match(report.takeaway, /错误价格和错误理由/);
});

run("legendary investor review gives CLEAN for disciplined supply-demand execution", () => {
  const exportData = buildLegendaryWorkbenchJsonExport(
    `
电子布涨价周期交易计划

一句话结论：电子布供应紧缺，涨价在即。

主腿：中材科技
对冲腿：中国巨石
弹性腿：宏和科技

产业判断：
电子布供不应求，景气上行，稼动率维持高位，覆铜板产业链排产紧张，公司具备定价权和提价能力。
`,
    []
  );
  const report = buildLegendaryInvestorReview(exportData, {
    traded_supply_demand_fact: true,
    primary_leg_had_pricing_power: true,
    hedge_leg_worked: true,
    confirm_leg_was_confirmed: true,
    chased_confirm_leg: false,
    respected_invalidation: true
  });

  assert.equal(report.playbook.key, "supply_demand_cycle");
  assert.equal(report.verdict, "CLEAN");
  assert.match(report.takeaway, /供需周期执行/);
});

run("legendary investor review runner prints json output", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-review-runner-"));
  const jsonPath = path.join(tempRoot, "legendary-investor-last-run.json");
  fs.writeFileSync(
    jsonPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    const lines = [];
    const report = runLegendaryInvestorReview(
      [
        "--json",
        "--json-file",
        jsonPath,
        "--fact",
        "traded_fact_not_story=true",
        "--fact",
        "primary_leg_was_stable=true",
        "--fact",
        "hedge_leg_worked=true",
        "--fact",
        "confirm_leg_was_confirmed=true",
        "--fact",
        "chased_confirm_leg=false",
        "--fact",
        "respected_invalidation=true"
      ],
      {
        config: { projectRoot: tempRoot },
        writer: {
          log(value) {
            lines.push(String(value));
          }
        }
      }
    );

    assert.equal(report.verdict, "CLEAN");
    assert.match(lines[0], /"verdict": "CLEAN"/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor review can persist latest review json", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-review-json-"));
  const jsonPath = path.join(tempRoot, "review.json");

  try {
    const written = writeLegendaryInvestorReviewJson(jsonPath, {
      verdict: "FAIL"
    });
    assert.equal(written, jsonPath);
    assert.equal(JSON.parse(fs.readFileSync(jsonPath, "utf8")).verdict, "FAIL");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor dashboard parser keeps file and write flags", () => {
  const parsed = parseLegendaryInvestorDashboardArgs([
    "--write",
    "--run-json-file",
    "handoff/run.json",
    "--checklist-state-file",
    "handoff/state.json"
  ]);

  assert.equal(parsed.write, true);
  assert.equal(parsed.runJsonFile, "handoff/run.json");
  assert.equal(parsed.checklistStateFile, "handoff/state.json");
});

run("legendary investor dashboard summarizes current run and checklist state", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-dashboard-build-"));
  const vaultPath = path.join(tempRoot, "vault");
  const config = {
    vaultPath,
    vaultName: "Test Vault",
    machineRoot: "08-ai-kb",
    projectRoot: tempRoot,
    obsidian: {
      cliCandidates: [],
      exeCandidates: []
    }
  };
  const runPath = path.join(tempRoot, "legendary-investor-last-run.json");
  const statePath = path.join(tempRoot, "legendary-investor-checklist-state.json");
  const decisionJsonPath = path.join(tempRoot, "legendary-investor-last-decision.json");
  const reviewJsonPath = path.join(tempRoot, "legendary-investor-last-review.json");
  const decisionPath = path.join(vaultPath, "08-ai-kb", "20-wiki", "syntheses", "Legendary-Investor-Decision-周一盘前执行版.md");
  fs.mkdirSync(path.dirname(decisionPath), { recursive: true });
  fs.writeFileSync(
    decisionPath,
    buildWikiFixture({
      wiki_kind: "synthesis",
      topic: "legendary investor decision",
      compiled_from: ["08-ai-kb/10-raw/manual/demo.md"],
      compiled_at: "2026-04-12T10:00:00+08:00",
      kb_date: "2026-04-12",
      kb_source_count: 1,
      dedup_key: "legendary investor decision::synthesis::demo",
      title: "Legendary-Investor-Decision-周一盘前执行版",
      body: "Decision"
    }),
    "utf8"
  );
  fs.writeFileSync(
    runPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );
  fs.writeFileSync(
    statePath,
    `${JSON.stringify(
      {
        schemaVersion: 1,
        updatedAt: "2026-04-12T11:00:00.000Z",
        items: {
          event_status: {
            checked: true,
            checkedAt: "2026-04-12T11:00:00.000Z",
            note: "已核验"
          }
        }
      },
      null,
      2
    )}\n`,
    "utf8"
  );
  fs.writeFileSync(`${decisionJsonPath}`, `${JSON.stringify({ verdict: "GO" }, null, 2)}\n`, "utf8");
  fs.writeFileSync(`${reviewJsonPath}`, `${JSON.stringify({ verdict: "FAIL" }, null, 2)}\n`, "utf8");

  try {
    const dashboard = buildLegendaryInvestorDashboard(config, {
      runPath,
      checklistStatePath: statePath,
      decisionJsonPath,
      reviewJsonPath,
      generatedAt: "2026-04-12T12:00:00.000Z"
    });
    const markdown = renderLegendaryInvestorDashboard(dashboard);

    assert.equal(dashboard.checklistProgress.completed, 1);
    assert.equal(dashboard.decisionData.verdict, "GO");
    assert.equal(dashboard.reviewData.verdict, "FAIL");
    assert.match(markdown, /Legendary-Investor-Decision-周一盘前执行版/);
    assert.match(markdown, /中国海油 0\.40 \+ 山东黄金 0\.25/);
    assert.match(markdown, /\[x\] 核验事件没有出现实质性缓和或协议突破 \| note=已核验/);
    assert.match(markdown, /decision_verdict: GO/);
    assert.match(markdown, /review_verdict: FAIL/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor dashboard shows supply-demand checklist labels", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-dashboard-supply-demand-"));
  const vaultPath = path.join(tempRoot, "vault");
  const config = {
    vaultPath,
    vaultName: "Test Vault",
    machineRoot: "08-ai-kb",
    projectRoot: tempRoot,
    obsidian: {
      cliCandidates: [],
      exeCandidates: []
    }
  };
  const runPath = path.join(tempRoot, "legendary-investor-last-run.json");
  const statePath = path.join(tempRoot, "legendary-investor-checklist-state.json");

  fs.writeFileSync(
    runPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
电子布涨价周期交易计划

一句话结论：电子布供应紧缺，涨价在即。

主腿：中材科技
对冲腿：中国巨石
弹性腿：宏和科技

产业判断：
电子布供不应求，景气上行，稼动率维持高位，覆铜板产业链排产紧张，公司具备定价权和提价能力。

标的\t主题入场\t确认入场\t失效
中材科技\t18.0-19.0\t过20.0放量\t跌破16.5
中国巨石\t15.0-16.0\t过17.0\t跌破14.0
宏和科技\t25.0-26.0\t放量过28.0\t跌破23.0
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );
  fs.writeFileSync(
    statePath,
    `${JSON.stringify(
      {
        schemaVersion: 1,
        updatedAt: "2026-04-13T11:00:00.000Z",
        items: {
          price_hike: {
            checked: true,
            checkedAt: "2026-04-13T11:00:00.000Z",
            note: "涨价核验完成"
          }
        }
      },
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    const dashboard = buildLegendaryInvestorDashboard(config, {
      runPath,
      checklistStatePath: statePath,
      generatedAt: "2026-04-13T12:00:00.000Z"
    });
    const markdown = renderLegendaryInvestorDashboard(dashboard);

    assert.equal(dashboard.checklistProgress.completed, 1);
    assert.match(markdown, /核验涨价\/提价是否仍在兑现/);
    assert.match(markdown, /\[x\] 核验涨价\/提价是否仍在兑现 \| note=涨价核验完成/);
    assert.match(markdown, /中材科技 0\.35 \+ 中国巨石 0\.10/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor dashboard runner prints markdown and can write note", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-dashboard-run-"));
  const vaultPath = path.join(tempRoot, "vault");
  const config = {
    vaultPath,
    vaultName: "Test Vault",
    machineRoot: "08-ai-kb",
    projectRoot: tempRoot,
    obsidian: {
      cliCandidates: [],
      exeCandidates: []
    }
  };
  const runPath = path.join(tempRoot, "legendary-investor-last-run.json");
  fs.writeFileSync(
    runPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    const lines = [];
    const printed = runLegendaryInvestorDashboard(
      ["--run-json-file", runPath],
      {
        config,
        writer: {
          log(value) {
            lines.push(String(value));
          }
        }
      }
    );
    assert.match(lines[0], /Legendary Investor Dashboard/);
    assert.ok(printed.markdown);

    const written = runLegendaryInvestorDashboard(
      ["--write", "--run-json-file", runPath],
      {
        config,
        writer: { log() {} }
      }
    );
    assert.equal(written.writeResult.path, "08-ai-kb/30-views/11-Legendary Investor/00-Execution Dashboard.md");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor runner parser keeps mode and write flags", () => {
  const parsed = parseLegendaryInvestorRunnerArgs([
    "--mode",
    "postclose",
    "--json-file",
    "handoff/run.json",
    "--facts-file",
    "handoff/facts.json",
    "--fact",
    "traded_fact_not_story=true",
    "--write-json",
    "--write-synthesis",
    "--write-dashboard",
    "--skip-links",
    "--skip-views"
  ]);

  assert.equal(parsed.mode, "postclose");
  assert.equal(parsed.jsonFile, "handoff/run.json");
  assert.equal(parsed.factsFile, "handoff/facts.json");
  assert.equal(parsed.facts.traded_fact_not_story, "true");
  assert.equal(parsed.writeJson, true);
  assert.equal(parsed.writeSynthesis, true);
  assert.equal(parsed.writeDashboard, true);
  assert.equal(parsed.skipLinks, true);
  assert.equal(parsed.skipViews, true);
});

run("legendary investor runner preopen chains checklist decision and dashboard", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-runner-preopen-"));
  const vaultPath = path.join(tempRoot, "vault");
  const config = {
    vaultPath,
    vaultName: "Test Vault",
    machineRoot: "08-ai-kb",
    projectRoot: tempRoot,
    obsidian: {
      cliCandidates: [],
      exeCandidates: []
    }
  };
  const runPath = path.join(tempRoot, "run.json");
  fs.writeFileSync(
    runPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    const lines = [];
    const result = runLegendaryInvestorRunner(
      [
        "--mode",
        "preopen",
        "--json-file",
        runPath,
        "--fact",
        "no_agreement=true",
        "--fact",
        "risk_unresolved=true",
        "--fact",
        "substantive_progress=false",
        "--fact",
        "primary_leg_confirmed=true"
      ],
      {
        config,
        writer: {
          log(value) {
            lines.push(String(value));
          }
        }
      }
    );

    assert.equal(result.mode, "preopen");
    assert.equal(result.decisionResult.verdict, "GO");
    assert.ok(result.dashboardResult.markdown);
    assert.match(lines.join("\n"), /=== CHECKLIST ===/);
    assert.match(lines.join("\n"), /=== DECISION ===/);
    assert.match(lines.join("\n"), /=== DASHBOARD ===/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary investor runner postclose chains review and dashboard", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-runner-postclose-"));
  const vaultPath = path.join(tempRoot, "vault");
  const config = {
    vaultPath,
    vaultName: "Test Vault",
    machineRoot: "08-ai-kb",
    projectRoot: tempRoot,
    obsidian: {
      cliCandidates: [],
      exeCandidates: []
    }
  };
  const runPath = path.join(tempRoot, "run.json");
  fs.writeFileSync(
    runPath,
    `${JSON.stringify(
      buildLegendaryWorkbenchJsonExport(
        `
中国海油主腿 + 招商南油弹性腿 + 山东黄金对冲腿

无协议
风险未解除
没有实质性续谈突破
`,
        []
      ),
      null,
      2
    )}\n`,
    "utf8"
  );

  try {
    const lines = [];
    const result = runLegendaryInvestorRunner(
      [
        "--mode",
        "postclose",
        "--json-file",
        runPath,
        "--fact",
        "traded_fact_not_story=true",
        "--fact",
        "primary_leg_was_stable=true",
        "--fact",
        "hedge_leg_worked=true",
        "--fact",
        "confirm_leg_was_confirmed=false",
        "--fact",
        "chased_confirm_leg=true",
        "--fact",
        "respected_invalidation=true"
      ],
      {
        config,
        writer: {
          log(value) {
            lines.push(String(value));
          }
        }
      }
    );

    assert.equal(result.mode, "postclose");
    assert.equal(result.reviewResult.verdict, "FAIL");
    assert.ok(result.dashboardResult.markdown);
    assert.match(lines.join("\n"), /=== REVIEW ===/);
    assert.match(lines.join("\n"), /=== DASHBOARD ===/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary writeback title builder uses first plan line", () => {
  const title = buildLegendaryArtifactTitle("Decision", {
    planInput: "周一盘前执行版\n\n一句话结论"
  });

  assert.equal(title, "Legendary Investor Decision - 周一盘前执行版");
});

run("legendary writeback resolves selected notes from exported metadata", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-writeback-notes-"));
  const vaultPath = path.join(tempRoot, "vault");
  const config = {
    vaultPath,
    vaultName: "Test Vault",
    machineRoot: "08-ai-kb",
    projectRoot: tempRoot,
    obsidian: {
      cliCandidates: [],
      exeCandidates: []
    }
  };
  const notePath = path.join(
    vaultPath,
    "08-ai-kb",
    "20-wiki",
    "syntheses",
    "Legendary-Investor-Workbench-v3.md"
  );
  fs.mkdirSync(path.dirname(notePath), { recursive: true });
  fs.writeFileSync(
    notePath,
    buildWikiFixture({
      wiki_kind: "synthesis",
      topic: "legendary investor",
      compiled_from: ["08-ai-kb/10-raw/manual/demo.md"],
      compiled_at: "2026-04-12T10:00:00+08:00",
      kb_date: "2026-04-12",
      kb_source_count: 1,
      dedup_key: "legendary investor::synthesis::demo",
      title: "Legendary-Investor-Workbench-v3",
      body: "Workbench"
    }),
    "utf8"
  );

  try {
    const selected = resolveLegendarySelectedNotes(config, {
      selectedNotes: [
        {
          title: "Legendary-Investor-Workbench-v3",
          relativePath: "08-ai-kb/20-wiki/syntheses/Legendary-Investor-Workbench-v3.md"
        }
      ]
    });

    assert.equal(selected.length, 1);
    assert.equal(selected[0].note.title, "Legendary-Investor-Workbench-v3");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary writeback writes synthesis note without refreshing links or views", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "legendary-writeback-run-"));
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

  try {
    const result = writeLegendaryArtifactSynthesis(
      config,
      {
        kindLabel: "Decision",
        query: "Legendary Investor Decision",
        topic: "legendary investor decision",
        answer: "## Decision\n\nGO",
        exportData: {
          planInput: "周一盘前执行版"
        }
      },
      {
        skipLinks: true,
        skipViews: true,
        allowFilesystemFallback: true,
        preferCli: false
      }
    );

    assert.equal(result.writeResult.action, "create");
    assert.equal(result.linkResult, null);
    assert.deepEqual(result.viewResults, []);
    assert.ok(
      fs.existsSync(
        path.join(
          config.vaultPath,
          "08-ai-kb",
          "20-wiki",
          "syntheses",
          "Legendary-Investor-Decision-周一盘前执行版.md"
        )
      )
    );
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("legendary reasoner routes valuation-style plans to the valuation-quality committee", () => {
  const summary = analyzeTradingPlan(`
如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？
`);
  const committee = buildRoundtableCommittee(summary);

  assert.equal(summary.roundtablePlaybookLabel, "估值与质量委员会");
  assert.deepEqual(
    committee.cards.map((card) => card.mentor),
    ["Buffett", "Howard Marks", "GMO"]
  );
  assert.equal(committee.cards[0].vote, "support");
  assert.equal(committee.cards[2].vote, "support");
});

run("legendary reasoner valuation fallback avoids event-driven jargon", () => {
  const workbench = buildLegendaryStageFallback(
    { key: "workbench_v3", title: "Workbench v3" },
    "如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？",
    [],
    []
  );
  const critic = buildLegendaryStageFallback(
    { key: "critic_mode", title: "Critic Mode" },
    "如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？",
    [],
    []
  );
  const actionCard = buildLegendaryStageFallback(
    { key: "final_action_card", title: "Final Action Card" },
    "如果这家公司护城河深、自由现金流强、资本配置优秀，但估值已经偏贵，还值得未来五年持有吗？",
    [],
    []
  );

  assert.match(workbench, /质量与估值判断/);
  assert.doesNotMatch(workbench, /无协议/);
  assert.match(critic, /高质量误当成任何价格都值得买/);
  assert.doesNotMatch(critic, /油运默认第二优先/);
  assert.match(actionCard, /核验企业质量、核验资本配置、核验现金流质量、核验当前价格是否仍有赔率/);
  assert.doesNotMatch(actionCard, /Monday pre-open checklist/);
  assert.doesNotMatch(actionCard, /headline/);
  assert.doesNotMatch(actionCard, /无协议/);
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
    "娑擃厼娴楀Ч鍊熸簠閸戠儤鎹ｉ柧鎾呯窗濮ｆ柧绨规潻顏傗偓浣风瑐濮瑰鈧胶顩撮懓鈧悳鑽ゆ嫅",
    "--compile",
    "--skip-links",
    "--timeout-ms",
    "300000"
  ]);

  assert.match(parsed.inputPath, /linqingv-result\.json$/);
  assert.deepEqual(parsed.postIds, ["2041135310852235487", "2041015554740543812"]);
  assert.equal(parsed.topic, "娑擃厼娴楀Ч鍊熸簠閸戠儤鎹ｉ柧鎾呯窗濮ｆ柧绨规潻顏傗偓浣风瑐濮瑰鈧胶顩撮懓鈧悳鑽ゆ嫅");
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
    <p class="h1">缁楊兛绨╃粩?鐠愌冪</p>
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
    sourcePath: "D:\\娑撳娴嘰\The Book of Elon.epub",
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

    const result = executeRollback(config, candidates);
    assert.equal(result.deleted, 1);
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

run("codex config candidate lister includes named non-backup profiles", () => {
  const codexHome = fs.mkdtempSync(path.join(tmpdir(), "obsidian-kb-config-candidates-"));

  try {
    fs.writeFileSync(path.join(codexHome, "config.toml"), 'model = "gpt-5.4"\n', "utf8");
    fs.writeFileSync(path.join(codexHome, "config - 登录自己的号.toml"), 'model = "gpt-5.4"\n', "utf8");
    fs.writeFileSync(path.join(codexHome, "config.toml.bak-20260410"), 'model = "gpt-5.4"\n', "utf8");

    const candidates = listCodexConfigCandidates({
      env: {
        CODEX_HOME: codexHome
      }
    });

    assert.equal(path.basename(candidates[0]), "config.toml");
    assert.equal(candidates.some((entry) => path.basename(entry) === "config - 登录自己的号.toml"), true);
    assert.equal(candidates.some((entry) => /bak/i.test(path.basename(entry))), false);
  } finally {
    fs.rmSync(codexHome, { recursive: true, force: true });
  }
});

run("healthy provider resolver falls back to a later config candidate after probe failure", async () => {
  const codexHome = fs.mkdtempSync(path.join(tmpdir(), "obsidian-kb-provider-fallback-"));

  try {
    fs.writeFileSync(
      path.join(codexHome, "config.toml"),
      `model_provider = "OpenAI"
model = "gpt-5.4"
[model_providers.OpenAI]
base_url = "https://broken-gateway.example/v1"
wire_api = "responses"
requires_openai_auth = true
`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(codexHome, "config - 登录自己的号.toml"),
      `model = "gpt-5.4"
`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(codexHome, "auth.json"),
      JSON.stringify({ OPENAI_API_KEY: "sk-official" }),
      "utf8"
    );

    const resolved = await resolveHealthyCodexLlmProvider({
      env: {
        CODEX_HOME: codexHome
      },
      callProvider: async (provider) => {
        if (provider.baseUrl.includes("broken-gateway")) {
          throw new Error("gateway empty response");
        }
        return {
          endpoint: `${provider.baseUrl}/responses`,
          outputText: "OK"
        };
      }
    });

    assert.equal(path.basename(resolved.configPath), "config - 登录自己的号.toml");
    assert.equal(resolved.provider.baseUrl, "https://api.openai.com/v1");
    assert.equal(resolved.attempts.length, 2);
    assert.equal(resolved.attempts[0].ok, false);
    assert.equal(resolved.attempts[1].ok, true);
  } finally {
    fs.rmSync(codexHome, { recursive: true, force: true });
  }
});

run("codex llm fallback retries the real prompt against a later config candidate", async () => {
  const codexHome = fs.mkdtempSync(path.join(tmpdir(), "obsidian-kb-provider-call-fallback-"));

  try {
    fs.writeFileSync(
      path.join(codexHome, "config.toml"),
      `model_provider = "OpenAI"
model = "gpt-5.4"
[model_providers.OpenAI]
base_url = "https://broken-gateway.example/v1"
wire_api = "responses"
requires_openai_auth = true
`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(codexHome, "config - 登录自己的号.toml"),
      `model = "gpt-5.4"
`,
      "utf8"
    );
    fs.writeFileSync(
      path.join(codexHome, "auth.json"),
      JSON.stringify({ OPENAI_API_KEY: "sk-official" }),
      "utf8"
    );

    const resolved = await callCodexLlmWithFallback("Long workbench prompt", {
      env: {
        CODEX_HOME: codexHome
      },
      callProvider: async (provider, prompt) => {
        assert.equal(prompt, "Long workbench prompt");
        if (provider.baseUrl.includes("broken-gateway")) {
          throw new Error("provider returned empty content");
        }
        return {
          endpoint: `${provider.baseUrl}/responses`,
          outputText: "OK from official route"
        };
      }
    });

    assert.equal(path.basename(resolved.configPath), "config - 登录自己的号.toml");
    assert.equal(resolved.response.outputText, "OK from official route");
    assert.equal(resolved.attempts.length, 2);
    assert.equal(resolved.attempts[0].ok, false);
    assert.equal(resolved.attempts[1].ok, true);
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

run("responses caller falls back to PowerShell on Windows TLS certificate failures", async () => {
  const provider = {
    providerName: "custom",
    model: "gpt-5.4",
    baseUrl: "https://gateway.example.test/v1",
    wireApi: "responses",
    apiKey: "sk-test"
  };
  const calls = [];

  const result = await callResponsesApi(provider, "Compile this note", {
    platform: "win32",
    fetchImpl: async () => {
      const error = new TypeError("fetch failed");
      error.cause = new Error("unable to verify the first certificate");
      throw error;
    },
    spawnSyncImpl(command, args, options) {
      calls.push({ command, args, options });
      assert.equal(command, "powershell.exe");
      assert.match(options.env.OBSIDIAN_KB_ENDPOINT, /https:\/\/gateway\.example\.test\/v1\/responses/);
      assert.equal(options.env.OBSIDIAN_KB_API_KEY, "sk-test");
      return {
        status: 0,
        stdout: JSON.stringify({
          output_text: "[{\"wiki_kind\":\"source\",\"title\":\"PS OK\",\"body\":\"Body\"}]"
        }),
        stderr: ""
      };
    }
  });

  assert.equal(calls.length, 1);
  assert.equal(result.endpoint, "https://gateway.example.test/v1/responses");
  assert.match(result.outputText, /PS OK/);
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

// ── Conversation Session Tests ──────────────────────────────────────

run("createSession returns valid session object", () => {
  const session = createSession({ topic: "test-topic" });
  assert.equal(typeof session.id, "string");
  assert.ok(session.id.startsWith("chat-"));
  assert.equal(session.topic, "test-topic");
  assert.deepEqual(session.turns, []);
  assert.deepEqual(session.contextKeywords, []);
});

run("addUserTurn and addAssistantTurn accumulate turns", () => {
  const session = createSession();
  addUserTurn(session, "What is momentum trading?");
  assert.equal(session.turns.length, 1);
  assert.equal(session.turns[0].role, "user");
  assert.equal(session.turns[0].content, "What is momentum trading?");

  addAssistantTurn(session, "Momentum trading is...", { selectedNotes: [] });
  assert.equal(session.turns.length, 2);
  assert.equal(session.turns[1].role, "assistant");
});

run("buildEnhancedQuery appends context keywords", () => {
  const session = createSession();
  addUserTurn(session, "What is CAN SLIM?");
  addAssistantTurn(session, "CAN SLIM is a growth stock methodology.", null);
  addUserTurn(session, "How does it relate to breakouts?");

  const enhanced = buildEnhancedQuery(session);
  assert.ok(enhanced.includes("breakouts"));
  // Should include accumulated keywords from first turn
  assert.ok(enhanced.includes("slim") || enhanced.includes("can"));
});

run("getLatestUserQuery returns last user message", () => {
  const session = createSession();
  addUserTurn(session, "first question");
  addAssistantTurn(session, "first answer", null);
  addUserTurn(session, "second question");
  assert.equal(getLatestUserQuery(session), "second question");
});

run("buildSessionTranscript produces markdown", () => {
  const session = createSession({ topic: "test" });
  addUserTurn(session, "Hello");
  addAssistantTurn(session, "Hi there", null);
  const transcript = buildSessionTranscript(session);
  assert.ok(transcript.includes("# Chat Session"));
  assert.ok(transcript.includes("**User**"));
  assert.ok(transcript.includes("**Assistant**"));
  assert.ok(transcript.includes("Hello"));
  assert.ok(transcript.includes("Hi there"));
});

run("dumpSessionToLog writes transcript file", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-session-log-"));
  try {
    const session = createSession();
    addUserTurn(session, "test query");
    addAssistantTurn(session, "test answer", null);
    const logPath = dumpSessionToLog(tempRoot, session);
    assert.ok(fs.existsSync(logPath));
    const content = fs.readFileSync(logPath, "utf8");
    assert.ok(content.includes("test query"));
    assert.ok(content.includes("test answer"));
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("buildConversationPrompt fills all template placeholders", () => {
  const template = "History: {{CONVERSATION_HISTORY}}\nQuery: {{QUERY}}\nTopic: {{TOPIC}}\nNotes: {{NOTE_CONTEXT}}";
  const session = createSession({ topic: "trading" });
  addUserTurn(session, "What is risk management?");
  const result = buildConversationPrompt(template, session, []);
  assert.ok(!result.includes("{{QUERY}}"));
  assert.ok(!result.includes("{{TOPIC}}"));
  assert.ok(!result.includes("{{NOTE_CONTEXT}}"));
  assert.ok(!result.includes("{{CONVERSATION_HISTORY}}"));
  assert.ok(result.includes("risk management"));
  assert.ok(result.includes("trading"));
});

// ── Cross-Topic Discovery Tests ─────────────────────────────────────

run("discoverCrossTopicCandidates finds pairs across topics", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/momentum-a.md",
      title: "Momentum Trading Basics",
      content: "Momentum trading involves buying stocks with strong upward price movement and relative strength.",
      frontmatter: { kb_type: "wiki", wiki_kind: "concept", topic: "trading-methodology", compiled_from: ["raw/a.md"] }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/psychology-b.md",
      title: "Trading Psychology Momentum",
      content: "Understanding momentum psychology requires discipline and managing emotions during strong price movement.",
      frontmatter: { kb_type: "wiki", wiki_kind: "concept", topic: "trading-psychology", compiled_from: ["raw/b.md"] }
    }
  ];

  const candidates = discoverCrossTopicCandidates(notes, { minSharedTokens: 2 });
  assert.ok(candidates.length > 0);
  assert.equal(candidates[0].noteA.topic !== candidates[0].noteB.topic, true);
});

run("discoverCrossTopicCandidates skips notes with shared compiled_from", () => {
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/a.md",
      title: "Concept Alpha",
      content: "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
      frontmatter: { kb_type: "wiki", wiki_kind: "concept", topic: "topic-a", compiled_from: ["raw/shared.md"] }
    },
    {
      relativePath: "08-ai-kb/20-wiki/concepts/b.md",
      title: "Concept Beta",
      content: "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
      frontmatter: { kb_type: "wiki", wiki_kind: "concept", topic: "topic-b", compiled_from: ["raw/shared.md"] }
    }
  ];

  const candidates = discoverCrossTopicCandidates(notes, { minSharedTokens: 3 });
  assert.equal(candidates.length, 0);
});

run("buildCrossTopicView produces markdown table", () => {
  const candidates = [
    {
      noteA: { path: "a.md", title: "Note A", topic: "topic-1", kind: "concept" },
      noteB: { path: "b.md", title: "Note B", topic: "topic-2", kind: "concept" },
      sharedTokens: ["alpha", "beta", "gamma"],
      sharedCount: 3,
      score: 3
    }
  ];
  const view = buildCrossTopicView(candidates);
  assert.ok(view.includes("Cross-Topic Synthesis Candidates"));
  assert.ok(view.includes("Note A"));
  assert.ok(view.includes("Note B"));
  assert.ok(view.includes("topic-1"));
  assert.ok(view.includes("topic-2"));
});

// ── Intent Rules Loading Tests ───────────────────────────────────────

run("intent rules load from config/intent-rules.json", () => {
  // Reset cache so it re-reads from disk
  _resetIntentRulesCache();
  // The config/intent-rules.json should have 4 rules
  // We test indirectly via selectRelevantWikiNotes with a FOMO query
  const notes = [
    {
      relativePath: "08-ai-kb/20-wiki/concepts/fomo.md",
      title: "FOMO Trading Pattern",
      content: "FOMO is a common trading psychology error involving fear of missing out on momentum.",
      frontmatter: { kb_type: "wiki", wiki_kind: "concept", topic: "trading-psychology" }
    }
  ];
  const results = selectRelevantWikiNotes(notes, "FOMO 复盘", { limit: 1 });
  // Should match via the trading-psychology intent rule
  assert.ok(results.length > 0);
  _resetIntentRulesCache();
});

// ── Query Telemetry Tests ────────────────────────────────────────────

run("logQueryTelemetry writes JSONL entry", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-telemetry-"));
  try {
    logQueryTelemetry(tempRoot, {
      query: "test query",
      topic: "test-topic",
      resultCount: 3,
      topPaths: ["a.md", "b.md", "c.md"],
      directMatchCount: 2,
      graphOnlyCount: 1,
      durationMs: 150,
      executed: true,
      intentLabel: "monetary-liquidity"
    });

    const logDir = path.join(tempRoot, "logs");
    const files = fs.readdirSync(logDir).filter((f) => f.startsWith("query-telemetry-"));
    assert.equal(files.length, 1);

    const content = fs.readFileSync(path.join(logDir, files[0]), "utf8").trim();
    const entry = JSON.parse(content);
    assert.equal(entry.query, "test query");
    assert.equal(entry.resultCount, 3);
    assert.equal(entry.executed, true);
    assert.equal(entry.intentLabel, "monetary-liquidity");
    assert.ok(entry.timestamp);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("logQueryTelemetry does not throw on write failure", () => {
  // Pass a non-writable path — should silently fail
  logQueryTelemetry("/nonexistent/path/that/cannot/exist", {
    query: "test",
    resultCount: 0,
    topPaths: [],
    durationMs: 0,
    executed: false
  });
  // If we get here without throwing, the test passes
});

// ── Query Feedback Tests ────────────────────────────────────────────

run("recordQueryFeedback writes JSONL entry", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-feedback-"));
  try {
    recordQueryFeedback(tempRoot, {
      query: "test query",
      topic: "test-topic",
      rating: 4,
      resultCount: 3,
      topPaths: ["a.md", "b.md"],
      intentLabel: "monetary-liquidity"
    });

    const logDir = path.join(tempRoot, "logs");
    const files = fs.readdirSync(logDir).filter((f) => f.startsWith("query-feedback-"));
    assert.equal(files.length, 1);

    const content = fs.readFileSync(path.join(logDir, files[0]), "utf8").trim();
    const entry = JSON.parse(content);
    assert.equal(entry.query, "test query");
    assert.equal(entry.rating, 4);
    assert.equal(entry.topic, "test-topic");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("recordQueryFeedback clamps rating to 1-5", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-feedback-clamp-"));
  try {
    recordQueryFeedback(tempRoot, { query: "q1", rating: 0, resultCount: 1, topPaths: [] });
    recordQueryFeedback(tempRoot, { query: "q2", rating: 10, resultCount: 1, topPaths: [] });

    const logDir = path.join(tempRoot, "logs");
    const files = fs.readdirSync(logDir).filter((f) => f.startsWith("query-feedback-"));
    const lines = fs.readFileSync(path.join(logDir, files[0]), "utf8").trim().split("\n");
    assert.equal(JSON.parse(lines[0]).rating, 1);
    assert.equal(JSON.parse(lines[1]).rating, 5);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("analyzeQueryFeedback returns empty result when no logs exist", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-feedback-empty-"));
  try {
    const result = analyzeQueryFeedback(tempRoot);
    assert.equal(result.totalEntries, 0);
    assert.equal(result.avgRating, 0);
    assert.deepEqual(result.suggestions, []);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("analyzeQueryFeedback detects weak topics", () => {
  const tempRoot = fs.mkdtempSync(path.join(process.cwd(), ".tmp-feedback-weak-"));
  try {
    // Write multiple low-rated entries for same topic
    for (let i = 0; i < 3; i++) {
      recordQueryFeedback(tempRoot, {
        query: `bad query ${i}`,
        topic: "weak-topic",
        rating: 1,
        resultCount: 0,
        topPaths: []
      });
    }
    recordQueryFeedback(tempRoot, {
      query: "good query",
      topic: "strong-topic",
      rating: 5,
      resultCount: 5,
      topPaths: ["a.md"]
    });

    const result = analyzeQueryFeedback(tempRoot);
    assert.equal(result.totalEntries, 4);
    assert.ok(result.suggestions.some((s) => s.type === "weak_topic" && s.topic === "weak-topic"));
    assert.ok(result.suggestions.some((s) => s.type === "zero_results"));
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

// ── Daily Validation Tests ──────────────────────────────────────────

run("daily validation parser keeps mode and fact flags", () => {
  const parsed = parseDailyValidationArgs([
    "--mode", "intraday",
    "--run-json-file", "handoff/custom-run.json",
    "--facts-file", "facts.json",
    "--fact", "no_agreement=true",
    "--fact", "risk_unresolved=true",
    "--write-json",
    "--output-json-file", "handoff/custom-validation.json",
    "--json",
    "--dry-run"
  ]);
  assert.equal(parsed.mode, "intraday");
  assert.equal(parsed.runJsonFile, "handoff/custom-run.json");
  assert.equal(parsed.factsFile, "facts.json");
  assert.equal(parsed.facts.no_agreement, "true");
  assert.equal(parsed.facts.risk_unresolved, "true");
  assert.equal(parsed.writeJson, true);
  assert.equal(parsed.outputJsonFile, "handoff/custom-validation.json");
  assert.equal(parsed.json, true);
  assert.equal(parsed.dryRun, true);
});

run("daily validation intraday facts contract builder normalizes fields", () => {
  const facts = buildIntradayFacts({
    trade_day: "2026-04-13",
    as_of: "2026-04-13T09:30:00Z",
    plan_source: "legendary-investor-last-run.json",
    market: "A-share",
    ticker_snapshots: [{ ticker: "600938.SS", price: 38.5 }],
    fact_flags: { no_agreement: true },
    operator_notes: "test"
  });
  assert.equal(facts.trade_day, "2026-04-13");
  assert.equal(facts.market, "A-share");
  assert.equal(facts.ticker_snapshots.length, 1);
  assert.equal(facts.fact_flags.no_agreement, true);
});

run("daily validation postclose facts contract builder normalizes fields", () => {
  const facts = buildPostcloseFacts({
    trade_day: "2026-04-13",
    as_of: "2026-04-13T15:30:00Z",
    execution_result: "主腿执行正常",
    missed_or_wrong_assumptions: ["油运高开追价"]
  });
  assert.equal(facts.trade_day, "2026-04-13");
  assert.equal(facts.execution_result, "主腿执行正常");
  assert.equal(facts.missed_or_wrong_assumptions.length, 1);
});

run("daily validation record builder normalizes all fields", () => {
  const record = buildValidationRecord({
    plan_id: "test-plan",
    trade_day: "2026-04-13",
    status: "success",
    decision_verdict: "GO",
    review_verdict: "CLEAN",
    why_right: ["主腿判断正确"],
    why_wrong: [],
    method_delta: ["继续沿用当前结构"],
    next_rule_changes: []
  });
  assert.equal(record.plan_id, "test-plan");
  assert.equal(record.status, "success");
  assert.equal(record.decision_verdict, "GO");
  assert.equal(record.review_verdict, "CLEAN");
  assert.equal(record.why_right.length, 1);
  assert.equal(record.method_delta.length, 1);
});

run("daily validation gives success for clean event-driven execution", () => {
  const exportData = {
    playbook: { key: "event_driven_risk", label: "事件驱动风险委员会" },
    summary: { primaryLeg: "中国海油", hedgeLeg: "山东黄金", confirmLeg: "招商南油" },
    committee: {
      verdict: { defaultStructure: "中国海油 0.40 + 山东黄金 0.25" },
      backupPlan: "只留山东黄金",
      primaryPlan: "中国海油 -> 山东黄金 -> 招商南油"
    },
    tradeCards: {
      confirm: { confirmEntry: "放量过 5.00" }
    }
  };
  const record = runDailyValidation(exportData, {
    mode: "postclose",
    intradayFacts: {
      trade_day: "2026-04-13",
      as_of: "2026-04-13T09:30:00Z",
      fact_flags: {
        no_agreement: true,
        risk_unresolved: true,
        primary_leg_confirmed: true,
        hedge_leg_confirmed: true
      }
    },
    postcloseFacts: {
      trade_day: "2026-04-13",
      as_of: "2026-04-13T15:30:00Z",
      fact_flags: {
        traded_fact_not_story: true,
        primary_leg_was_stable: true,
        hedge_leg_worked: true,
        confirm_leg_was_confirmed: true,
        chased_confirm_leg: false,
        respected_invalidation: true
      }
    }
  });
  assert.equal(record.status, "success");
  assert.equal(record.decision_verdict, "GO");
  assert.equal(record.review_verdict, "CLEAN");
  assert.ok(record.why_right.length > 0);
});

run("daily validation gives fail for undisciplined execution", () => {
  const exportData = {
    playbook: { key: "event_driven_risk", label: "事件驱动风险委员会" },
    summary: { primaryLeg: "中国海油", hedgeLeg: "山东黄金", confirmLeg: "招商南油" },
    committee: {
      verdict: { defaultStructure: "中国海油 0.40 + 山东黄金 0.25" },
      backupPlan: "只留山东黄金",
      primaryPlan: "中国海油 -> 山东黄金 -> 招商南油"
    },
    tradeCards: {
      confirm: { confirmEntry: "放量过 5.00" }
    }
  };
  const record = runDailyValidation(exportData, {
    mode: "postclose",
    intradayFacts: {
      trade_day: "2026-04-13",
      as_of: "2026-04-13T09:30:00Z",
      fact_flags: {
        no_agreement: true,
        risk_unresolved: true,
        primary_leg_confirmed: true
      }
    },
    postcloseFacts: {
      trade_day: "2026-04-13",
      as_of: "2026-04-13T15:30:00Z",
      fact_flags: {
        traded_fact_not_story: false,
        primary_leg_was_stable: true,
        hedge_leg_worked: true,
        confirm_leg_was_confirmed: false,
        chased_confirm_leg: true,
        respected_invalidation: true
      }
    }
  });
  assert.equal(record.status, "fail");
  assert.equal(record.review_verdict, "FAIL");
  assert.ok(record.why_wrong.length > 0);
});

run("daily validation intraday mode gives too_early without postclose", () => {
  const exportData = {
    playbook: { key: "supply_demand_cycle", label: "供需周期委员会" },
    summary: { primaryLeg: "中材科技", hedgeLeg: "中国巨石", confirmLeg: "宏和科技" },
    committee: {
      verdict: { defaultStructure: "中材科技 0.35 + 中国巨石 0.10" },
      backupPlan: "只留中国巨石",
      primaryPlan: "中材科技 -> 中国巨石 -> 宏和科技"
    }
  };
  const record = runDailyValidation(exportData, {
    mode: "intraday",
    intradayFacts: {
      trade_day: "2026-04-13",
      as_of: "2026-04-13T10:00:00Z",
      fact_flags: {}
    }
  });
  assert.equal(record.status, "too_early");
  assert.equal(record.review_verdict, null);
});

run("daily validation supply-demand gives success when all facts confirm", () => {
  const exportData = {
    playbook: { key: "supply_demand_cycle", label: "供需周期委员会" },
    summary: { primaryLeg: "中材科技", hedgeLeg: "中国巨石", confirmLeg: "宏和科技" },
    committee: {
      verdict: { defaultStructure: "中材科技 0.35 + 中国巨石 0.10", downgradeSequence: "先减宏和科技" },
      backupPlan: "只留中国巨石",
      primaryPlan: "中材科技 -> 中国巨石 -> 宏和科技（仅在放量过28.0后）"
    },
    tradeCards: {
      confirm: { confirmEntry: "放量过28.0" }
    }
  };
  const record = runDailyValidation(exportData, {
    mode: "postclose",
    intradayFacts: {
      trade_day: "2026-04-13",
      fact_flags: {
        price_hike_confirmed: true,
        supply_shortage_confirmed: true,
        high_utilization_confirmed: true,
        primary_leg_confirmed: true,
        confirm_leg_confirmed: true
      }
    },
    postcloseFacts: {
      trade_day: "2026-04-13",
      fact_flags: {
        traded_supply_demand_fact: true,
        primary_leg_had_pricing_power: true,
        hedge_leg_worked: true,
        confirm_leg_was_confirmed: true,
        chased_confirm_leg: false,
        respected_invalidation: true
      }
    }
  });
  assert.equal(record.status, "success");
  assert.equal(record.decision_verdict, "GO");
  assert.equal(record.review_verdict, "CLEAN");
});

run("daily validation renders markdown output", () => {
  const record = buildValidationRecord({
    plan_id: "电子布涨价周期交易计划",
    trade_day: "2026-04-13",
    status: "partial",
    decision_verdict: "GO",
    review_verdict: "MIXED",
    why_right: ["主腿判断正确"],
    why_wrong: ["弹性腿追高"],
    method_delta: ["下次等确认"],
    next_rule_changes: ["不确认不追"],
    fact_layer_issues: ["涨价兑现未完全确认"],
    timing_issues: ["弹性腿提前放大"]
  });
  const rendered = renderValidationRecord(record);
  assert.ok(rendered.includes("Daily Trade Plan Validation"));
  assert.ok(rendered.includes("partial"));
  assert.ok(rendered.includes("主腿判断正确"));
  assert.ok(rendered.includes("弹性腿追高"));
  assert.ok(rendered.includes("Method Delta"));
  assert.ok(rendered.includes("Next Rule Changes"));
});

run("daily validation cli dry-run does not crash", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "daily-validation-dry-"));
  const runPath = path.join(tempRoot, "legendary-investor-last-run.json");
  fs.writeFileSync(runPath, JSON.stringify({
    playbook: { key: "event_driven_risk", label: "事件驱动风险委员会" },
    summary: { primaryLeg: "中国海油", hedgeLeg: "山东黄金", confirmLeg: "招商南油" },
    committee: {
      verdict: { defaultStructure: "中国海油 0.40 + 山东黄金 0.25" },
      backupPlan: "只留山东黄金",
      primaryPlan: "中国海油 -> 山东黄金 -> 招商南油"
    }
  }, null, 2));

  try {
    const logs = [];
    const result = runDailyValidationCli(
      ["--mode", "postclose", "--run-json-file", runPath, "--dry-run"],
      {
        config: { projectRoot: tempRoot, vaultPath: tempRoot, machineRoot: tempRoot },
        writer: { log: (msg) => logs.push(msg), error: (msg) => logs.push(msg) }
      }
    );
    assert.equal(result.dryRun, true);
    assert.ok(logs.some((l) => l.includes("DRY RUN")));
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("daily validation cli postclose writes json output", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "daily-validation-write-"));
  const runPath = path.join(tempRoot, "legendary-investor-last-run.json");
  fs.mkdirSync(path.join(tempRoot, "handoff"), { recursive: true });
  fs.writeFileSync(runPath, JSON.stringify({
    playbook: { key: "event_driven_risk", label: "事件驱动风险委员会" },
    summary: { primaryLeg: "中国海油", hedgeLeg: "山东黄金", confirmLeg: "招商南油" },
    committee: {
      verdict: { defaultStructure: "中国海油 0.40 + 山东黄金 0.25" },
      backupPlan: "只留山东黄金",
      primaryPlan: "中国海油 -> 山东黄金 -> 招商南油"
    },
    tradeCards: { confirm: { confirmEntry: "放量过 5.00" } }
  }, null, 2));

  try {
    const logs = [];
    const result = runDailyValidationCli(
      [
        "--mode", "postclose",
        "--run-json-file", runPath,
        "--fact", "traded_fact_not_story=true",
        "--fact", "primary_leg_was_stable=true",
        "--fact", "hedge_leg_worked=true",
        "--fact", "respected_invalidation=true",
        "--fact", "no_agreement=true",
        "--fact", "risk_unresolved=true",
        "--fact", "primary_leg_confirmed=true",
        "--fact", "trade_day=2026-04-13",
        "--write-json"
      ],
      {
        config: { projectRoot: tempRoot, vaultPath: tempRoot, machineRoot: tempRoot },
        writer: { log: (msg) => logs.push(msg), error: (msg) => logs.push(msg) }
      }
    );
    assert.ok(result.status);
    assert.ok(result.jsonWritePath);
    assert.ok(fs.existsSync(result.jsonWritePath));
    const persisted = JSON.parse(fs.readFileSync(result.jsonWritePath, "utf8"));
    assert.equal(persisted.decision_verdict, result.decision_verdict);

    // Dated file should be in handoff/ and match the ledger pattern
    assert.ok(result.jsonWritePath.includes("legendary-investor-validation-"));
    // "last" copy should also exist
    const lastPath = path.join(tempRoot, "handoff", "legendary-investor-last-validation.json");
    assert.ok(fs.existsSync(lastPath));

    // Ledger should find exactly 1 record (the dated file, not the "last" copy)
    const records = loadValidationRecords(path.join(tempRoot, "handoff"));
    assert.equal(records.length, 1);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

run("daily validation X signals are classified into supporting and contradicting", () => {
  const exportData = {
    playbook: { key: "event_driven_risk", label: "事件驱动风险委员会" },
    summary: { primaryLeg: "中国海油", hedgeLeg: "山东黄金", confirmLeg: "招商南油" },
    committee: {
      verdict: { defaultStructure: "中国海油 0.40 + 山东黄金 0.25" },
      backupPlan: "只留山东黄金",
      primaryPlan: "中国海油 -> 山东黄金 -> 招商南油"
    }
  };
  const record = runDailyValidation(exportData, {
    mode: "postclose",
    postcloseFacts: {
      trade_day: "2026-04-13",
      fact_flags: {
        traded_fact_not_story: true,
        primary_leg_was_stable: true,
        hedge_leg_worked: true,
        respected_invalidation: true,
        no_agreement: true,
        risk_unresolved: true,
        primary_leg_confirmed: true
      }
    },
    xSignals: [
      { direction: "supporting", handle: "Ariston_Macro", content: "Oil risk premium still elevated" },
      { direction: "contradicting", handle: "LinQingV", content: "Talks may resume soon" }
    ]
  });
  assert.equal(record.x_supporting_signals.length, 1);
  assert.equal(record.x_contradicting_signals.length, 1);
  assert.ok(record.x_explanation.includes("1 supporting"));
  assert.ok(record.x_explanation.includes("1 contradicting"));
});

// ── Validation Ledger Tests ─────────────────────────────────────────

run("validation ledger aggregates multiple records correctly", () => {
  const records = [
    { trade_day: "2026-04-10", status: "success", why_wrong: [], next_rule_changes: [], method_delta: [] },
    { trade_day: "2026-04-11", status: "partial", why_wrong: ["[Review] 招商南油 没有等确认就被放大"], next_rule_changes: ["不确认不追"], method_delta: ["下次等确认"] },
    { trade_day: "2026-04-12", status: "fail", why_wrong: ["[Review] 追高了弹性腿", "[Review] 脑补升级"], next_rule_changes: [], method_delta: [] },
    { trade_day: "2026-04-13", status: "success", why_wrong: [], next_rule_changes: [], method_delta: [] }
  ];
  const agg = aggregateValidationRecords(records);
  assert.equal(agg.total, 4);
  assert.equal(agg.win_rate, 0.5);
  assert.equal(agg.status_distribution.success, 2);
  assert.equal(agg.status_distribution.partial, 1);
  assert.equal(agg.status_distribution.fail, 1);
  assert.ok(agg.failure_modes.length > 0);
  assert.equal(agg.recent_streak.type, "win");
  assert.equal(agg.recent_streak.length, 1);
});

run("validation ledger handles empty records", () => {
  const agg = aggregateValidationRecords([]);
  assert.equal(agg.total, 0);
  assert.equal(agg.win_rate, null);
  assert.equal(agg.failure_modes.length, 0);
});

run("validation ledger renders markdown output", () => {
  const agg = aggregateValidationRecords([
    { trade_day: "2026-04-13", status: "success", why_wrong: [], next_rule_changes: [], method_delta: [] }
  ]);
  const rendered = renderValidationLedger(agg);
  assert.ok(rendered.includes("Validation Ledger"));
  assert.ok(rendered.includes("Win Rate"));
  assert.ok(rendered.includes("100.0%"));
});

run("validation ledger loads records from directory", () => {
  const tempRoot = fs.mkdtempSync(path.join(tmpdir(), "validation-ledger-"));
  try {
    fs.writeFileSync(path.join(tempRoot, "legendary-investor-validation-2026-04-13.json"), JSON.stringify({
      trade_day: "2026-04-13", status: "success", why_wrong: [], next_rule_changes: [], method_delta: []
    }));
    fs.writeFileSync(path.join(tempRoot, "legendary-investor-validation-2026-04-14.json"), JSON.stringify({
      trade_day: "2026-04-14", status: "fail", why_wrong: ["追高"], next_rule_changes: [], method_delta: []
    }));
    fs.writeFileSync(path.join(tempRoot, "unrelated.json"), JSON.stringify({ foo: "bar" }));

    const records = loadValidationRecords(tempRoot);
    assert.equal(records.length, 2);
    assert.equal(records[0].trade_day, "2026-04-13");
    assert.equal(records[1].trade_day, "2026-04-14");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

await Promise.allSettled(pendingRuns);

if (process.exitCode) {
  process.exit(process.exitCode);
}
