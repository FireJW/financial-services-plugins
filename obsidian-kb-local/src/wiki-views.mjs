import fs from "node:fs";
import path from "node:path";
import { findRawNotes, findWikiNotes } from "./compile-pipeline.mjs";
import { formatIso8601Tz } from "./frontmatter.mjs";
import { loadGraphifyWorkspaceStatuses } from "./graphify-topic-workspaces.mjs";
import { writeNote } from "./note-writer.mjs";
import {
  getCodexThreadAuditLogPath,
  getCodexThreadCaptureStatusPath,
  getCodexThreadRecoveryQueuePath,
  getDashboardPath,
  getFinanceBookReferencesPath,
  getGraphInsightsPath,
  getGraphInsightsIndexPath,
  getGraphTopicStatusPath,
  getNetworkIndexIndexPath,
  getNetworkTraceIndexPath,
  getOpenQuestionsPath,
  getPoliticalEconomyBookReferencesPath,
  getReferenceMapAuditPath,
  getSourcesByTopicPath,
  getStaleNotesPath,
  getTradingPsychologyMentorIndexPath,
  getTradingPsychologyMentorReferenceCasesDir,
  getTradingPsychologyMentorReferenceCasesIndexPath
} from "./view-paths.mjs";

export function getWikiIndexPath(machineRoot) {
  return `${machineRoot}/20-wiki/_index.md`;
}

export function getWikiLogPath(machineRoot) {
  return `${machineRoot}/20-wiki/_log.md`;
}

export function buildWikiViewNotes(config, options = {}) {
  const timestamp = options.timestamp || formatIso8601Tz(new Date());
  const rawNotes = findRawNotes(config.vaultPath, config.machineRoot, {
    onlyQueued: false
  });
  const wikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {});
  const logDirectory = path.join(config.projectRoot, "logs");
  const compileLogs = loadJsonlEntries(logDirectory, /^compile-\d{4}-\d{2}-\d{2}\.jsonl$/);
  const compileErrors = loadJsonlEntries(
    logDirectory,
    /^compile-errors-\d{4}-\d{2}-\d{2}\.jsonl$/
  );
  const verifyLogs = loadJsonlEntries(
    logDirectory,
    /^verify-codex-thread-capture-\d{4}-\d{2}-\d{2}\.jsonl$/
  );
  const captureLogs = loadJsonlEntries(
    logDirectory,
    /^capture-codex-thread-\d{4}-\d{2}-\d{2}\.jsonl$/
  );
  const captureBatchLogs = loadJsonlEntries(
    logDirectory,
    /^capture-codex-thread-batch-\d{4}-\d{2}-\d{2}\.jsonl$/
  );
  const reconcileLogs = loadJsonlEntries(
    logDirectory,
    /^reconcile-codex-thread-capture-\d{4}-\d{2}-\d{2}\.jsonl$/
  );

  return [
    {
      path: getDashboardPath(config.machineRoot),
      content: buildDashboardContent(config)
    },
    {
      path: getWikiIndexPath(config.machineRoot),
      content: buildWikiIndexContent(config, {
        timestamp,
        rawNotes,
        wikiNotes
      })
    },
    {
      path: getWikiLogPath(config.machineRoot),
      content: buildWikiLogContent(config, {
        timestamp,
        compileLogs,
        compileErrors
      })
    },
    {
      path: getReferenceMapAuditPath(config.machineRoot),
      content: buildReferenceMapAuditContent(config, {
        timestamp,
        wikiNotes
      })
    },
    {
      path: getGraphTopicStatusPath(config.machineRoot),
      content: buildGraphTopicStatusContent(config, { timestamp })
    },
    {
      path: getCodexThreadCaptureStatusPath(config.machineRoot),
      content: buildCodexThreadCaptureStatusContent(config, {
        timestamp,
        rawNotes,
        wikiNotes,
        verifyLogs,
        reconcileLogs
      })
    },
    {
      path: getCodexThreadRecoveryQueuePath(config.machineRoot),
      content: buildCodexThreadRecoveryQueueContent(config, {
        timestamp,
        reconcileLogs
      })
    },
    {
      path: getCodexThreadAuditLogPath(config.machineRoot),
      content: buildCodexThreadAuditLogContent(config, {
        timestamp,
        rawNotes,
        captureLogs,
        captureBatchLogs,
        verifyLogs,
        reconcileLogs
      })
    },
    {
      path: getGraphInsightsIndexPath(config.machineRoot),
      content: buildFolderIndexContent("Graph Insights", `${config.machineRoot}/30-views/07-Graph Insights`, "Graph Insights")
    },
    {
      path: getNetworkIndexIndexPath(config.machineRoot),
      content: buildFolderIndexContent("Network Index", `${config.machineRoot}/30-views/08-Network Index`, "Network Index")
    },
    {
      path: getNetworkTraceIndexPath(config.machineRoot),
      content: buildFolderIndexContent("Network Trace", `${config.machineRoot}/30-views/09-Network Trace`, "Network Trace")
    },
    {
      path: getTradingPsychologyMentorIndexPath(config.machineRoot),
      content: buildTradingPsychologyMentorIndexContent(config.machineRoot)
    },
    {
      path: getTradingPsychologyMentorReferenceCasesIndexPath(config.machineRoot),
      content: buildTradingPsychologyReferenceCasesIndexContent(config.machineRoot)
    }
  ];
}

export function refreshWikiViews(config, options = {}) {
  const notes = Array.isArray(options.notes) ? options.notes : buildWikiViewNotes(config, options);
  const results = [];
  const allowFilesystemFallback = options.allowFilesystemFallback ?? true;
  let preferCli = options.preferCli ?? true;
  const writeNoteImpl = typeof options.writeNote === "function" ? options.writeNote : writeNote;

  for (const note of notes) {
    const result = writeNoteImpl(config, note, {
      allowFilesystemFallback,
      preferCli,
      cliRunTimeoutMs: options.cliRunTimeoutMs
    });
    results.push(result);

    if (preferCli && allowFilesystemFallback && result.mode === "filesystem-fallback" && result.cliAttempted) {
      preferCli = false;
    }
  }

  return results;
}

export function buildDashboardContent(config) {
  const root = config.machineRoot;

  return `# KB Dashboard

## Quick Links

- [[${root}/20-wiki/_index|Wiki Index]]
- [[${root}/20-wiki/_log|Wiki Log]]
- [[${getStaleNotesPath(root).replace(/\.md$/, "")}|Stale Notes]]
- [[${getOpenQuestionsPath(root).replace(/\.md$/, "")}|Open Questions]]
- [[${getSourcesByTopicPath(root).replace(/\.md$/, "")}|Sources by Topic]]
- [[${getPoliticalEconomyBookReferencesPath(root).replace(/\.md$/, "")}|Political Economy Book References]]
- [[${getFinanceBookReferencesPath(root).replace(/\.md$/, "")}|Finance Book References]]
- [[${getReferenceMapAuditPath(root).replace(/\.md$/, "")}|Reference Map Audit]]
- [[${getGraphTopicStatusPath(root).replace(/\.md$/, "")}|Graph Topic Status]]
- [[${getCodexThreadCaptureStatusPath(root).replace(/\.md$/, "")}|Codex Thread Capture Status]]
- [[${getCodexThreadRecoveryQueuePath(root).replace(/\.md$/, "")}|Codex Thread Recovery Queue]]
- [[${getCodexThreadAuditLogPath(root).replace(/\.md$/, "")}|Codex Thread Audit Log]]
- [[${getGraphInsightsIndexPath(root).replace(/\.md$/, "")}|Graph Insights Hub]]
- [[${getNetworkIndexIndexPath(root).replace(/\.md$/, "")}|Network Index Hub]]
- [[${getNetworkTraceIndexPath(root).replace(/\.md$/, "")}|Network Trace Hub]]
- [[${getTradingPsychologyMentorIndexPath(root).replace(/\.md$/, "")}|Trading Psychology Mentor Hub]]
- [[${getTradingPsychologyMentorReferenceCasesIndexPath(root).replace(/\.md$/, "")}|Reference Cases Hub]]

## Trading Fast Lane

- [[${root}/20-wiki/syntheses/开仓前30秒决策卡片|开仓前30秒决策卡片]]
- [[${root}/20-wiki/syntheses/收盘后3分钟复盘卡片|收盘后3分钟复盘卡片]]
- [[${root}/20-wiki/syntheses/交易系统类型选择器-breakout、discretionary、trend-following|交易系统类型选择器]]
- [[${root}/20-wiki/syntheses/交易计划模板-入场理由、失效条件、止损、目标、仓位|交易计划模板]]
- [[${root}/20-wiki/syntheses/退出动作模板-全平、分批减仓、移动止损、结构失效退出|退出动作模板]]
- [[${root}/20-wiki/syntheses/仓位计算模板-账户风险、单位风险、可下手数|仓位计算模板]]
- [[${root}/20-wiki/syntheses/失败交易归因模板-系统错、执行错、情绪错、环境错|失败交易归因模板]]

## Political Economy Fast Lane

- [[${root}/20-wiki/syntheses/political-economy-book-reference-hub|中国经济与政治经济学书籍参考地图]]
- [[${getPoliticalEconomyBookReferencesPath(root).replace(/\.md$/, "")}|Political Economy Book References]]
- [[${root}/20-wiki/sources/置身事内：中国政府与经济发展|置身事内：中国政府与经济发展]]
- [[${root}/20-wiki/sources/中国国家治理的制度逻辑：一个组织学研究|中国国家治理的制度逻辑：一个组织学研究]]
- [[${root}/20-wiki/sources/解读中国经济(增订版)|解读中国经济(增订版)]]
- [[${root}/20-wiki/sources/大崛起：中国经济的增长与转型|大崛起：中国经济的增长与转型]]
- [[${root}/20-wiki/concepts/土地财政与土地金融|土地财政与土地金融]]
- [[${root}/20-wiki/concepts/地方政府事权划分的三大原则|地方政府事权划分的三大原则]]
- [[${root}/20-wiki/concepts/地方化产权保护机制|地方化产权保护机制]]
- [[${root}/20-wiki/concepts/民本主义政治经济学|民本主义政治经济学]]

## Maintenance Commands

\`\`\`powershell
cmd /c "cd obsidian-kb-local && npm run refresh-trading-suite"
cmd /c "cd obsidian-kb-local && npm run refresh-trading-suite -- --skip-health-check"
cmd /c "cd obsidian-kb-local && npm run refresh-political-economy-suite"
cmd /c "cd obsidian-kb-local && npm run refresh-political-economy-suite -- --force"
cmd /c "cd obsidian-kb-local && npm run refresh-political-economy-suite -- --with-compile"
\`\`\`

## Stats

\`\`\`dataview
TABLE WITHOUT ID
  length(filter(rows, (r) => r.kb_type = "raw")) AS "Raw",
  length(filter(rows, (r) => r.kb_type = "wiki")) AS "Wiki",
  length(filter(rows, (r) => r.status = "queued")) AS "Queued",
  length(filter(rows, (r) => r.review_state = "draft")) AS "Drafts"
FROM "${root}"
WHERE kb_type
FLATTEN "all" AS group
GROUP BY group
\`\`\`

## Trading Card Stack

\`\`\`dataview
TABLE topic, kb_date, kb_source_count
FROM "${root}/20-wiki/syntheses"
WHERE contains(file.name, "卡片")
SORT kb_date DESC
\`\`\`

## Political Economy Sources

\`\`\`dataview
TABLE topic, kb_date, review_state, kb_source_count
FROM "${root}/20-wiki/sources"
WHERE contains(topic, "中国") OR contains(topic, "政治经济学") OR contains(file.name, "置身事内") OR contains(file.name, "治理")
SORT kb_date DESC
LIMIT 12
\`\`\`

## Recent Raw

\`\`\`dataview
TABLE source_type, topic, status, kb_date
FROM "${root}/10-raw"
WHERE kb_type = "raw"
SORT kb_date DESC
LIMIT 20
\`\`\`

## Recent Wiki

\`\`\`dataview
TABLE wiki_kind, topic, review_state, kb_date, kb_source_count
FROM "${root}/20-wiki"
WHERE kb_type = "wiki"
SORT kb_date DESC
LIMIT 20
\`\`\`

## Queued for Compilation

\`\`\`dataview
TABLE source_type, topic, kb_date
FROM "${root}/10-raw"
WHERE status = "queued"
SORT kb_date ASC
\`\`\`

## Open Drafts

\`\`\`dataview
TABLE wiki_kind, topic, kb_date
FROM "${root}/20-wiki"
WHERE review_state = "draft"
SORT kb_date DESC
\`\`\`

## Recent Mentor Sessions

\`\`\`dataview
TABLE file.link AS "Session", file.mtime AS "Updated"
FROM "${root}/30-views/10-Trading Psychology Mentor/01-Sessions"
SORT file.mtime DESC
LIMIT 8
\`\`\`

## Recent Reference Cases

\`\`\`dataview
TABLE file.link AS "Case", file.mtime AS "Updated"
FROM "${root}/30-views/10-Trading Psychology Mentor/03-Reference Cases"
WHERE file.name != "00-Index"
SORT file.mtime DESC
LIMIT 8
\`\`\`
`;
}

export function buildCodexThreadCaptureStatusContent(config, params = {}) {
  const timestamp = params.timestamp || formatIso8601Tz(new Date());
  const rawNotes = Array.isArray(params.rawNotes)
    ? params.rawNotes
    : findRawNotes(config.vaultPath, config.machineRoot, {
        onlyQueued: false
      });
  const wikiNotes = Array.isArray(params.wikiNotes)
    ? params.wikiNotes
    : findWikiNotes(config.vaultPath, config.machineRoot, {});
  const verifyLogs = Array.isArray(params.verifyLogs) ? params.verifyLogs : [];
  const reconcileLogs = Array.isArray(params.reconcileLogs) ? params.reconcileLogs : [];
  const summary = summarizeCodexThreadCaptures(rawNotes, wikiNotes);
  const recentVerifyRuns = summarizeCodexThreadCaptureAuditRuns(verifyLogs)
    .filter((row) => !row.synthetic)
    .slice(0, 8);
  const recentReconcileRuns = summarizeCodexThreadCaptureAuditRuns(reconcileLogs)
    .filter((row) => !row.synthetic)
    .slice(0, 8);
  const latestRecoveryRun = recentReconcileRuns.find((row) => row.missing > 0) || null;
  const latestMissingThreads =
    latestRecoveryRun?.missingThreadUris ||
    recentVerifyRuns.find((row) => row.missing > 0)?.missingThreadUris ||
    [];

  return `# Codex Thread Capture Status

Generated at: ${timestamp}

## Summary

- tracked thread URIs: ${summary.threadCount}
- raw captures: ${summary.rawRows.length}
- compiled raw captures: ${summary.compiledRawCount}
- queued raw captures: ${summary.queuedRawCount}
- derived wiki notes: ${summary.wikiRows.length}

## Recent Raw Captures

${formatMarkdownTable(
  ["Date", "Title", "Thread", "Status"],
  summary.rawRows.slice(0, 15).map((row) => [
    row.kbDate,
    toWikiLink(row.path, row.title),
    formatThreadLabel(row.threadUri),
    row.status
  ])
)}

## Derived Wiki Notes

${formatMarkdownTable(
  ["Kind", "Wiki Note", "Thread", "Compiled At"],
  summary.wikiRows.slice(0, 20).map((row) => [
    row.wikiKind,
    toWikiLink(row.path, row.title),
    formatThreadLabel(row.threadUri),
    row.compiledAt
  ])
)}

## Recent Verify Runs

${formatMarkdownTable(
  ["Timestamp", "Run", "Total", "Captured", "Missing", "Raw Matches", "Wiki Matches"],
  recentVerifyRuns.map((row) => [
    row.timestamp,
    formatRunId(row.runId),
    String(row.total),
    String(row.captured),
    String(row.missing),
    String(row.rawMatchCount),
    String(row.wikiMatchCount)
  ])
)}

## Recent Reconcile Runs

${formatMarkdownTable(
  ["Timestamp", "Run", "Total", "Captured", "Missing", "Body Files", "Output"],
  recentReconcileRuns.map((row) => [
    row.timestamp,
    formatRunId(row.runId),
    String(row.total),
    String(row.captured),
    String(row.missing),
    String(row.bodyFileCount),
    truncateInline(row.outputDir, 80)
  ])
)}

## Latest Missing Threads

${formatBulletList(latestMissingThreads, (threadUri) => `- \`${threadUri}\``)}

## Latest Recovery Package

${formatRecoveryPackageSection(latestRecoveryRun, config)}

## Verification Commands

\`\`\`powershell
cmd /c "cd obsidian-kb-local && npm run verify-codex-thread-capture -- --thread-id <thread-id>"
cmd /c "cd obsidian-kb-local && npm run reconcile-codex-thread-capture -- --output-dir .tmp-codex-thread-reconcile --manifest <manifest>"
\`\`\`
`;
}

export function buildCodexThreadRecoveryQueueContent(config, params = {}) {
  const timestamp = params.timestamp || formatIso8601Tz(new Date());
  const reconcileLogs = Array.isArray(params.reconcileLogs) ? params.reconcileLogs : [];
  const pendingRuns = summarizeCodexThreadCaptureAuditRuns(reconcileLogs)
    .filter((row) => !row.synthetic && row.missing > 0)
    .slice(0, 20);

  return `# Codex Thread Recovery Queue

Generated at: ${timestamp}

## Pending Recovery Runs

${formatMarkdownTable(
  ["Timestamp", "Missing", "Body Files", "Manifest", "Output"],
  pendingRuns.map((row) => [
    row.timestamp,
    String(row.missing),
    String(row.bodyFileCount),
    truncateInline(row.manifestPath, 80),
    truncateInline(row.outputDir, 80)
  ])
)}

## Pending Missing Threads

${formatBulletList(
  pendingRuns.flatMap((row) => row.missingThreadUris),
  (threadUri) => `- \`${threadUri}\``
)}

## Replay Commands

${formatBulletList(
  pendingRuns,
  (row) =>
    `- \`${row.timestamp}\`: \`node scripts/capture-codex-thread-batch.mjs --manifest '${row.manifestPath}' --compile --timeout-ms 240000\``
)}
`;
}

export function buildCodexThreadAuditLogContent(config, params = {}) {
  const timestamp = params.timestamp || formatIso8601Tz(new Date());
  const rawNotes = Array.isArray(params.rawNotes)
    ? params.rawNotes
    : findRawNotes(config.vaultPath, config.machineRoot, {
        onlyQueued: false
      });
  const captureLogs = Array.isArray(params.captureLogs) ? params.captureLogs : [];
  const captureBatchLogs = Array.isArray(params.captureBatchLogs) ? params.captureBatchLogs : [];
  const verifyLogs = Array.isArray(params.verifyLogs) ? params.verifyLogs : [];
  const reconcileLogs = Array.isArray(params.reconcileLogs) ? params.reconcileLogs : [];
  const events = buildCodexThreadAuditEvents(
    rawNotes,
    captureLogs,
    captureBatchLogs,
    verifyLogs,
    reconcileLogs
  );

  return `# Codex Thread Audit Log

Generated at: ${timestamp}

## Summary

- capture events: ${events.filter((row) => row.type === "capture").length}
- batch capture runs: ${events.filter((row) => row.type === "capture-batch").length}
- verify events: ${events.filter((row) => row.type === "verify").length}
- reconcile events: ${events.filter((row) => row.type === "reconcile").length}
- visible audit events: ${events.length}

## Recent Events

${formatMarkdownTable(
  ["Timestamp", "Run", "Type", "Thread", "Status", "Artifact"],
  events.slice(0, 40).map((row) => [
    row.timestamp,
    formatRunId(row.runId),
    row.type,
    row.thread,
    row.status,
    row.artifact
  ])
)}

## Notes

- Capture events prefer explicit JSONL logs and fall back to codex-backed raw notes for older history.
- Verify and reconcile events come from durable JSONL audit logs under \`obsidian-kb-local/logs\`.
- Synthetic validation runs are hidden from this page.
`;
}

export function buildGraphTopicStatusContent(config, params = {}) {
  const timestamp = params.timestamp || formatIso8601Tz(new Date());
  const rows = loadGraphifyWorkspaceStatuses(config.projectRoot);

  return `# Graph Topic Status

Generated at: ${timestamp}

## Summary

- topics: ${rows.length}
- pass: ${rows.filter((row) => row.status === "pass").length}
- warn: ${rows.filter((row) => row.status === "warn").length}
- fail: ${rows.filter((row) => row.status === "fail").length}
- missing graph: ${rows.filter((row) => row.status === "missing-graph").length}

## Topics

${formatMarkdownTable(
  [
    "Topic",
    "Status",
    "Nodes",
    "Edges",
    "Communities",
    "Selection",
    "Warnings",
    "Errors"
  ],
  rows.map((row) => [
    `[[${getGraphInsightsPath(config.machineRoot, row.topic).replace(/\.md$/, "")}|${row.topic}]]`,
    row.status,
    String(row.nodes),
    String(row.edges),
    String(row.communities),
    row.selectionMode,
    String(row.warningCount),
    String(row.errorCount)
  ])
)}
`;
}

export function buildWikiIndexContent(config, params) {
  const { timestamp, rawNotes, wikiNotes } = params;
  const kindCounts = countBy(wikiNotes, (note) => note.frontmatter.wiki_kind || "unknown");
  const topicRows = buildTopicCoverageRows(rawNotes, wikiNotes).slice(0, 20);
  const recentRaw = sortByDate(rawNotes, "captured_at").slice(0, 15);
  const recentWiki = sortByDate(wikiNotes, "compiled_at").slice(0, 20);

  return `# Wiki Index

Machine-maintained entrypoint for compiled knowledge in \`${config.machineRoot}/20-wiki\`.

Generated at: ${timestamp}

## Quick Links

- [[${config.machineRoot}/20-wiki/_log|Wiki Log]]
- [[${getDashboardPath(config.machineRoot).replace(/\.md$/, "")}|KB Dashboard]]
- [[${getStaleNotesPath(config.machineRoot).replace(/\.md$/, "")}|Stale Notes]]
- [[${getOpenQuestionsPath(config.machineRoot).replace(/\.md$/, "")}|Open Questions]]
- [[${getSourcesByTopicPath(config.machineRoot).replace(/\.md$/, "")}|Sources by Topic]]
- [[${getPoliticalEconomyBookReferencesPath(config.machineRoot).replace(/\.md$/, "")}|Political Economy Book References]]
- [[${getFinanceBookReferencesPath(config.machineRoot).replace(/\.md$/, "")}|Finance Book References]]
- [[${getReferenceMapAuditPath(config.machineRoot).replace(/\.md$/, "")}|Reference Map Audit]]

## Coverage Summary

- Raw notes: ${rawNotes.length}
- Wiki notes: ${wikiNotes.length}
- Concepts: ${kindCounts.concept || 0}
- Entities: ${kindCounts.entity || 0}
- Sources: ${kindCounts.source || 0}
- Syntheses: ${kindCounts.synthesis || 0}

## Top Topics by Coverage

${formatMarkdownTable(
  ["Topic", "Raw", "Wiki", "Latest Wiki"],
  topicRows.map((row) => [row.topic, String(row.rawCount), String(row.wikiCount), row.latestWiki])
)}

## Recent Raw Notes

${formatBulletList(
  recentRaw,
  (note) =>
    `- ${note.frontmatter.kb_date || ""} ${toWikiLink(note.relativePath, note.frontmatter.topic || note.title)} (${note.frontmatter.source_type || "raw"}, status=${note.frontmatter.status || "unknown"})`
)}

## Recent Wiki Notes

${formatBulletList(
  recentWiki,
  (note) =>
    `- ${note.frontmatter.kb_date || ""} ${toWikiLink(note.relativePath, note.title)} (${note.frontmatter.wiki_kind || "wiki"}, topic=${note.frontmatter.topic || ""})`
)}
`;
}

function buildFolderIndexContent(title, folderPath, prefix) {
  return `# ${title} Hub

## Notes

\`\`\`dataview
TABLE file.link AS "Note", file.mtime AS "Updated"
FROM "${folderPath}"
WHERE file.name != "00-Index"
SORT file.mtime DESC
\`\`\`

## Scope

- Prefix: \`${prefix}\`
`;
}

function buildTradingPsychologyMentorIndexContent(machineRoot) {
  const base = `${machineRoot}/30-views/10-Trading Psychology Mentor`;
  return `# Trading Psychology Mentor Hub

- [[${getTradingPsychologyMentorReferenceCasesIndexPath(machineRoot).replace(/\.md$/, "")}|Reference Cases Index]]

## Sessions

\`\`\`dataview
TABLE file.link AS "Session", file.mtime AS "Updated"
FROM "${base}/01-Sessions"
SORT file.mtime DESC
\`\`\`

## Templates

\`\`\`dataview
TABLE file.link AS "Template", file.mtime AS "Updated"
FROM "${base}/02-Templates"
SORT file.name ASC
\`\`\`

## Reference Cases

\`\`\`dataview
TABLE file.link AS "Reference", file.mtime AS "Updated"
FROM "${base}/03-Reference Cases"
SORT file.mtime DESC
\`\`\`
`;
}

function buildTradingPsychologyReferenceCasesIndexContent(machineRoot) {
  const base = getTradingPsychologyMentorReferenceCasesDir(machineRoot);
  return `# Trading Psychology Reference Cases

## By Date

\`\`\`dataview
TABLE regexreplace(file.name, "^([0-9]{4}-[0-9]{2}-[0-9]{2}).*$", "$1") AS "Date", file.link AS "Case"
FROM "${base}"
WHERE file.name != "00-Index"
SORT regexreplace(file.name, "^([0-9]{4}-[0-9]{2}-[0-9]{2}).*$", "$1") DESC, file.name ASC
\`\`\`

## By Topic

\`\`\`dataview
TABLE regexreplace(file.name, "^[0-9]{4}-[0-9]{2}-[0-9]{2}-", "") AS "Topic", file.link AS "Case"
FROM "${base}"
WHERE file.name != "00-Index"
SORT file.name DESC
\`\`\`

## Notes

- 建议把人工整理后的长期可回看案例都放在这个目录
- 文件名最好保持 \`YYYY-MM-DD-主题\` 形式，方便按日期回看
`;
}

function summarizeCodexThreadCaptures(rawNotes, wikiNotes) {
  const rawRows = rawNotes
    .filter((note) => String(note.frontmatter?.source_url || "").startsWith("codex://threads/"))
    .map((note) => ({
      path: note.relativePath,
      title: note.title,
      threadUri: String(note.frontmatter?.source_url || ""),
      kbDate: String(note.frontmatter?.kb_date || ""),
      status: String(note.frontmatter?.status || "unknown")
    }))
    .sort((left, right) => right.kbDate.localeCompare(left.kbDate) || left.title.localeCompare(right.title));

  const rawPathToThread = new Map(rawRows.map((row) => [row.path, row.threadUri]));
  const wikiRows = wikiNotes
    .map((note) => {
      const compiledFrom = Array.isArray(note.frontmatter?.compiled_from)
        ? note.frontmatter.compiled_from
        : [];
      const dedupKey = String(note.frontmatter?.dedup_key || "");
      const compiledThread = compiledFrom.find((entry) => rawPathToThread.has(entry));
      const threadUri =
        (compiledThread && rawPathToThread.get(compiledThread)) ||
        rawRows.find((row) => dedupKey.includes(row.threadUri))?.threadUri ||
        "";
      if (!threadUri) {
        return null;
      }
      return {
        path: note.relativePath,
        title: note.title,
        wikiKind: String(note.frontmatter?.wiki_kind || "wiki"),
        threadUri,
        compiledAt: String(note.frontmatter?.compiled_at || "")
      };
    })
    .filter(Boolean)
    .sort(
      (left, right) =>
        right.compiledAt.localeCompare(left.compiledAt) || left.title.localeCompare(right.title)
    );

  return {
    threadCount: new Set(rawRows.map((row) => row.threadUri)).size,
    rawRows,
    wikiRows,
    compiledRawCount: rawRows.filter((row) => row.status === "compiled").length,
    queuedRawCount: rawRows.filter((row) => row.status === "queued").length
  };
}

function summarizeCodexThreadCaptureAuditRuns(entries) {
  return entries
    .map((entry) => ({
      timestamp: String(entry.timestamp || ""),
      total: Number(entry.total || 0),
      captured: Number(entry.captured || 0),
      missing: Number(entry.missing || 0),
      rawMatchCount: Number(entry.raw_match_count || 0),
      wikiMatchCount: Number(entry.wiki_match_count || 0),
      bodyFileCount: Number(entry.body_file_count || 0),
      outputDir: String(entry.output_dir || ""),
      reportPath: String(entry.report_path || ""),
      manifestPath: String(entry.manifest_path || ""),
      runId: String(entry.run_id || ""),
      synthetic: entry.synthetic === true,
      missingThreadUris: Array.isArray(entry.missing_thread_uris)
        ? entry.missing_thread_uris.map((value) => String(value))
        : []
    }))
    .sort((left, right) => right.timestamp.localeCompare(left.timestamp));
}

function buildCodexThreadAuditEvents(rawNotes, captureLogs, captureBatchLogs, verifyLogs, reconcileLogs) {
  const loggedCaptureEvents = summarizeCaptureAuditRuns(captureLogs)
    .filter((row) => !row.synthetic)
    .map((row) => ({
      timestamp: row.timestamp,
      runId: row.runId,
      type: "capture",
      thread: formatThreadLabel(row.threadUri),
      status: row.rawStatus || "unknown",
      artifact: row.rawNotePath
        ? toWikiLink(row.rawNotePath, basenameNoExtension(row.rawNotePath))
        : row.title || row.topic || "(unknown)"
    }));
  const batchCaptureEvents = summarizeCaptureBatchAuditRuns(captureBatchLogs)
    .filter((row) => !row.synthetic)
    .map((row) => ({
      timestamp: row.timestamp,
      runId: row.runId,
      type: "capture-batch",
      thread: `${row.completed}/${row.total} completed`,
      status: `failed=${row.failed}`,
      artifact: row.manifestPath ? truncateInline(row.manifestPath, 90) : "(unknown)"
    }));
  const loggedCapturePaths = new Set(
    loggedCaptureEvents
      .map((row) => extractLinkedPathFromArtifact(row.artifact))
      .filter(Boolean)
  );
  const fallbackCaptureEvents = rawNotes
    .filter((note) => String(note.frontmatter?.source_url || "").startsWith("codex://threads/"))
    .filter((note) => !loggedCapturePaths.has(note.relativePath))
    .map((note) => ({
      timestamp: String(note.frontmatter?.captured_at || note.frontmatter?.kb_date || ""),
      runId: "",
      type: "capture",
      thread: formatThreadLabel(String(note.frontmatter?.source_url || "")),
      status: String(note.frontmatter?.status || "unknown"),
      artifact: toWikiLink(note.relativePath, note.title)
    }));

  const verifyEvents = summarizeCodexThreadCaptureAuditRuns(verifyLogs)
    .filter((row) => !row.synthetic)
    .map((row) => ({
      timestamp: row.timestamp,
      runId: row.runId,
      type: "verify",
      thread:
        row.missingThreadUris.length > 0
          ? `${row.missingThreadUris.length} missing`
          : `${row.captured} captured`,
      status: `captured=${row.captured}, missing=${row.missing}`,
      artifact: `${row.rawMatchCount} raw / ${row.wikiMatchCount} wiki`
    }));

  const reconcileEvents = summarizeCodexThreadCaptureAuditRuns(reconcileLogs)
    .filter((row) => !row.synthetic)
    .map((row) => ({
      timestamp: row.timestamp,
      runId: row.runId,
      type: "reconcile",
      thread:
        row.missingThreadUris.length > 0
          ? `${row.missingThreadUris.length} missing`
          : "fully captured",
      status: `captured=${row.captured}, missing=${row.missing}`,
      artifact: row.manifestPath
        ? truncateInline(row.manifestPath, 90)
        : truncateInline(row.outputDir, 90)
    }));

  return [
    ...loggedCaptureEvents,
    ...batchCaptureEvents,
    ...fallbackCaptureEvents,
    ...verifyEvents,
    ...reconcileEvents
  ].sort((left, right) =>
    String(right.timestamp).localeCompare(String(left.timestamp))
  );
}

function summarizeCaptureAuditRuns(entries) {
  return entries
    .map((entry) => ({
      timestamp: String(entry.timestamp || ""),
      threadUri: String(entry.thread_uri || ""),
      topic: String(entry.topic || ""),
      title: String(entry.title || ""),
      rawNotePath: String(entry.raw_note_path || ""),
      rawStatus: String(entry.raw_status || ""),
      runId: String(entry.run_id || ""),
      synthetic: entry.synthetic === true
    }))
    .sort((left, right) => right.timestamp.localeCompare(left.timestamp));
}

function summarizeCaptureBatchAuditRuns(entries) {
  return entries
    .map((entry) => ({
      timestamp: String(entry.timestamp || ""),
      manifestPath: String(entry.manifest_path || ""),
      total: Number(entry.total || 0),
      completed: Number(entry.completed || 0),
      failed: Number(entry.failed || 0),
      runId: String(entry.run_id || ""),
      synthetic: entry.synthetic === true
    }))
    .sort((left, right) => right.timestamp.localeCompare(left.timestamp));
}

function extractLinkedPathFromArtifact(text) {
  const match = String(text || "").match(/\[\[([^|\]]+)/);
  return match ? normalizeMarkdownLinkPath(match[1]) : "";
}

function normalizeMarkdownLinkPath(value) {
  return String(value || "").replace(/\\/g, "/");
}

function formatRecoveryPackageSection(row, config) {
  if (!row) {
    return "_No pending recovery package._";
  }

  const commandLines = row.manifestPath
    ? [
        `Set-Location '${escapePowershellSingleQuoted(config?.projectRoot || ".")}'`,
        `node scripts/capture-codex-thread-batch.mjs --manifest '${escapePowershellSingleQuoted(
          row.manifestPath
        )}' --compile --timeout-ms 240000`
      ]
    : [];

  const lines = [
    `- Latest run: \`${row.timestamp}\``,
    `- Missing threads: ${row.missing}`,
    `- Output dir: \`${row.outputDir || "(unknown)"}\``,
    `- Report: \`${row.reportPath || "(unknown)"}\``,
    `- Missing manifest: \`${row.manifestPath || "(unknown)"}\``
  ];

  if (commandLines.length > 0) {
    lines.push("");
    lines.push("```powershell");
    lines.push(...commandLines);
    lines.push("```");
  }

  return lines.join("\n");
}

function formatRunId(runId) {
  const text = String(runId || "").trim();
  if (!text) {
    return "(n/a)";
  }
  return truncateInline(text, 24);
}

function escapePowershellSingleQuoted(value) {
  return String(value ?? "").replace(/'/g, "''");
}

function formatThreadLabel(threadUri) {
  const text = String(threadUri || "").trim();
  if (!text) {
    return "(unknown)";
  }
  return text.replace(/^codex:\/\/threads\//, "");
}

export function buildWikiLogContent(config, params) {
  const { timestamp, compileLogs, compileErrors } = params;
  const groupedSuccesses = summarizeCompileLogEntries(compileLogs).slice(0, 25);
  const recentErrors = compileErrors
    .slice()
    .sort((left, right) => String(right.timestamp).localeCompare(String(left.timestamp)))
    .slice(0, 15);

  return `# Wiki Log

Machine-maintained activity log for \`${config.machineRoot}\`.

Generated at: ${timestamp}

## Recent Successful Compiles

${formatMarkdownTable(
  ["Timestamp", "Raw Note", "Actions", "Wiki Notes"],
  groupedSuccesses.map((entry) => [
    entry.timestamp,
    toWikiLink(entry.rawPath, basenameNoExtension(entry.rawPath)),
    entry.actionSummary,
    entry.noteSummary
  ])
)}

## Recent Compile Errors

${formatMarkdownTable(
  ["Timestamp", "Raw Note", "Model", "Error"],
  recentErrors.map((entry) => [
    entry.timestamp || "",
    entry.raw_path ? toWikiLink(entry.raw_path, basenameNoExtension(entry.raw_path)) : "(unknown)",
    entry.model || "",
    truncateInline(entry.error || "", 160)
  ])
)}
`;
}

export function buildReferenceMapAuditContent(config, params) {
  const { timestamp, wikiNotes } = params;
  const rows = collectReferenceMapAuditRows(wikiNotes);
  const zeroEntryRows = rows.filter((row) => row.entries === 0);
  const seedsOnlyRows = rows.filter(
    (row) => row.entries > 0 && row.recommended === 0 && row.searchReady === 0
  );
  const anthologyRows = rows.filter((row) => row.anthologyCandidate);
  const mixedCitationRows = rows.filter(
    (row) => row.entries >= 50 && row.searchReady > 0 && row.searchReady / row.entries < 0.4
  );
  const recoveredRows = rows.filter((row) => row.backmatterRecovered && row.entries > 0);

  return `# Reference Map Audit

Generated at: ${timestamp}

## Summary

- Reference maps scanned: ${rows.length}
- Zero-entry maps: ${zeroEntryRows.length}
- Seeds-only maps: ${seedsOnlyRows.length}
- Anthology candidates: ${anthologyRows.length}
- Anthology split seeds: ${rows.reduce((sum, row) => sum + row.anthologySubBooks, 0)}
- Mixed-citation pressure maps: ${mixedCitationRows.length}
- Backmatter-recovered maps: ${recoveredRows.length}
- Political view: [[${getPoliticalEconomyBookReferencesPath(config.machineRoot).replace(/\.md$/, "")}|Political Economy Book References]]
- Finance view: [[${getFinanceBookReferencesPath(config.machineRoot).replace(/\.md$/, "")}|Finance Book References]]

## Zero-Entry Maps

${formatMarkdownTable(
  ["Map", "Raw", "Flags", "Next Move"],
  zeroEntryRows.map((row) => [
    toWikiLink(row.mapPath, row.title),
    row.rawPath ? toWikiLink(row.rawPath, basenameNoExtension(row.rawPath)) : "(missing)",
    formatAuditFlags(row),
    row.anthologyCandidate
      ? row.anthologySubBooks > 0
        ? `Promote ${row.anthologySubBooks} detected sub-book seeds first.`
        : "Split anthology / omnibus into sub-books first."
      : "Inspect raw note for non-standard bibliography layout or confirm there is no reference section."
  ])
)}

## Seeds-Only Maps

${formatMarkdownTable(
  ["Map", "Entries", "Sections", "Flags", "Why It Matters"],
  seedsOnlyRows.map((row) => [
    toWikiLink(row.mapPath, row.title),
    String(row.entries),
    String(row.sections),
    formatAuditFlags(row),
    "Recovered citation seeds exist, but none are promoted to book-grade titles yet."
  ])
)}

## Anthology Candidates

${formatMarkdownTable(
  ["Map", "Raw", "Entries", "Split Seeds", "Flags"],
  anthologyRows.map((row) => [
    toWikiLink(row.mapPath, row.title),
    row.rawPath ? toWikiLink(row.rawPath, basenameNoExtension(row.rawPath)) : "(missing)",
    String(row.entries),
    String(row.anthologySubBooks),
    formatAuditFlags(row)
  ])
)}

## Mixed-Citation Pressure

${formatMarkdownTable(
  ["Map", "Entries", "Search-Ready", "Ratio", "Flags"],
  mixedCitationRows.map((row) => [
    toWikiLink(row.mapPath, row.title),
    String(row.entries),
    String(row.searchReady),
    formatPercent(row.searchReady / row.entries),
    formatAuditFlags(row)
  ])
)}

## Backmatter-Recovered Maps

${formatMarkdownTable(
  ["Map", "Entries", "Strict", "Search-Ready", "Flags"],
  recoveredRows.map((row) => [
    toWikiLink(row.mapPath, row.title),
    String(row.entries),
    String(row.strict),
    String(row.searchReady),
    formatAuditFlags(row)
  ])
)}
`;
}

function collectReferenceMapAuditRows(wikiNotes) {
  return wikiNotes
    .filter((note) => isReferenceMapNote(note))
    .map((note) => {
      const metrics = parseReferenceMapMetrics(note.content || "");
      const rawPath = Array.isArray(note.frontmatter?.compiled_from)
        ? note.frontmatter.compiled_from[0] || ""
        : "";
      const title = stripReferenceMapSuffix(note.frontmatter?.topic || note.title || basenameNoExtension(note.relativePath));
      const anthologyCandidate = looksLikeAnthologyTitle(title) || metrics.anthologySubBooks > 0;
      const backmatterRecovered = /^(?:###)\s+(?:Notes\b|Notes\s*>|BIBLIOGRAPHY\b|Bibliography\b|Endnotes\b)/m.test(
        note.content || ""
      );

      return {
        mapPath: note.relativePath,
        rawPath,
        title,
        anthologyCandidate,
        backmatterRecovered,
        ...metrics
      };
    })
    .sort((left, right) => {
      if (right.entries !== left.entries) {
        return right.entries - left.entries;
      }
      return left.title.localeCompare(right.title);
    });
}

function isReferenceMapNote(note) {
  const relativePath = String(note?.relativePath || "").replace(/\\/g, "/");
  const topic = String(note?.frontmatter?.topic || "");
  return (
    relativePath.includes("/20-wiki/sources/") &&
    (/-reference-map\.md$/i.test(relativePath) || / Reference Map$/i.test(topic))
  );
}

function parseReferenceMapMetrics(content) {
  const text = String(content || "");
  return {
    entries: parseMetric(text, /Extracted reference entries:\s*(\d+)/i),
    sections: parseMetric(text, /Reference sections:\s*(\d+)/i),
    strict: parseMetric(text, /Strict book titles:\s*(\d+)/i),
    searchReady: parseMetric(text, /Search-ready book titles:\s*(\d+)/i),
    recommended: parseMetric(text, /Recommended titles:\s*(\d+)/i),
    anthologySubBooks: parseMetric(text, /Anthology sub-books detected:\s*(\d+)/i)
  };
}

function parseMetric(content, pattern) {
  return Number.parseInt(String(content).match(pattern)?.[1] || "0", 10) || 0;
}

function stripReferenceMapSuffix(value) {
  return String(value || "").replace(/\s+Reference Map$/i, "").trim();
}

function looksLikeAnthologyTitle(value) {
  const compact = String(value || "").trim();
  if (!compact) {
    return false;
  }

  return /(?:全集|系列|全\d+册|共\d+册|三部曲|套装|套書)|(?:trilogy|anthology|collected works|collection)$/i.test(
    compact
  );
}

function formatAuditFlags(row) {
  const flags = [];
  if (row.anthologyCandidate) {
    flags.push("anthology");
  }
  if (row.anthologySubBooks > 0) {
    flags.push(`split-seeds:${row.anthologySubBooks}`);
  }
  if (row.backmatterRecovered && row.entries > 0) {
    flags.push("backmatter");
  }
  if (row.entries === 0) {
    flags.push("zero-entry");
  } else if (row.recommended === 0 && row.searchReady === 0) {
    flags.push("seeds-only");
  }
  if (row.entries >= 50 && row.searchReady > 0 && row.searchReady / row.entries < 0.4) {
    flags.push("mixed-citation");
  }

  return flags.length > 0 ? flags.join(", ") : "ok";
}

function formatPercent(value) {
  if (!Number.isFinite(value)) {
    return "0%";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function summarizeCompileLogEntries(entries) {
  const grouped = new Map();

  for (const entry of entries) {
    const rawPath = String(entry.raw_path || "").trim();
    const timestamp = String(entry.timestamp || "").trim();
    if (!rawPath || !timestamp) {
      continue;
    }

    const key = `${timestamp}::${rawPath}`;
    const group = grouped.get(key) || {
      timestamp,
      rawPath,
      actions: new Map(),
      notePaths: []
    };

    const action = String(entry.action || "update");
    group.actions.set(action, (group.actions.get(action) || 0) + 1);
    if (typeof entry.path === "string" && entry.path.trim() !== "") {
      group.notePaths.push(entry.path.trim());
    }
    grouped.set(key, group);
  }

  return [...grouped.values()]
    .map((group) => ({
      timestamp: group.timestamp,
      rawPath: group.rawPath,
      actionSummary: [...group.actions.entries()]
        .map(([action, count]) => `${action} x${count}`)
        .join(", "),
      noteSummary: summarizeNotePaths(group.notePaths)
    }))
    .sort((left, right) => String(right.timestamp).localeCompare(String(left.timestamp)));
}

function buildTopicCoverageRows(rawNotes, wikiNotes) {
  const rows = new Map();

  for (const note of rawNotes) {
    const topic = String(note.frontmatter.topic || note.title || "").trim() || "(untitled)";
    const row = rows.get(topic) || {
      topic,
      rawCount: 0,
      wikiCount: 0,
      latestWiki: ""
    };
    row.rawCount += 1;
    rows.set(topic, row);
  }

  for (const note of wikiNotes) {
    const topic = String(note.frontmatter.topic || note.title || "").trim() || "(untitled)";
    const row = rows.get(topic) || {
      topic,
      rawCount: 0,
      wikiCount: 0,
      latestWiki: ""
    };
    row.wikiCount += 1;
    const compiledAt = String(note.frontmatter.compiled_at || "").trim();
    if (compiledAt && (!row.latestWiki || compiledAt > row.latestWiki)) {
      row.latestWiki = compiledAt;
    }
    rows.set(topic, row);
  }

  return [...rows.values()].sort((left, right) => {
    if (right.wikiCount !== left.wikiCount) {
      return right.wikiCount - left.wikiCount;
    }
    if (right.rawCount !== left.rawCount) {
      return right.rawCount - left.rawCount;
    }
    return left.topic.localeCompare(right.topic);
  });
}

function loadJsonlEntries(directory, filePattern) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  const files = fs
    .readdirSync(directory)
    .filter((fileName) => filePattern.test(fileName))
    .sort()
    .map((fileName) => path.join(directory, fileName));

  const entries = [];
  for (const filePath of files) {
    const content = fs.readFileSync(filePath, "utf8");
    for (const line of content.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      try {
        entries.push(JSON.parse(trimmed));
      } catch {
        continue;
      }
    }
  }

  return entries;
}

function sortByDate(notes, fieldName) {
  return notes
    .slice()
    .sort((left, right) =>
      String(right.frontmatter?.[fieldName] || "").localeCompare(String(left.frontmatter?.[fieldName] || ""))
    );
}

function countBy(values, selector) {
  const counts = {};
  for (const value of values) {
    const key = selector(value);
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}

function formatMarkdownTable(headers, rows) {
  if (!rows || rows.length === 0) {
    return "_No entries yet._";
  }

  const lines = [
    `| ${headers.join(" | ")} |`,
    `| ${headers.map(() => "---").join(" | ")} |`
  ];

  for (const row of rows) {
    lines.push(`| ${row.map((cell) => sanitizeTableCell(cell)).join(" | ")} |`);
  }

  return lines.join("\n");
}

function formatBulletList(items, formatter) {
  if (!items || items.length === 0) {
    return "_No entries yet._";
  }
  return items.map((item) => formatter(item)).join("\n");
}

function summarizeNotePaths(notePaths) {
  if (!notePaths || notePaths.length === 0) {
    return "(none)";
  }

  const unique = [...new Set(notePaths)];
  const preview = unique.slice(0, 3).map((notePath) => toWikiLink(notePath, basenameNoExtension(notePath)));
  const suffix = unique.length > 3 ? ` +${unique.length - 3} more` : "";
  return `${preview.join(", ")}${suffix}`;
}

function sanitizeTableCell(value) {
  return String(value ?? "")
    .replace(/\|/g, "\\|")
    .replace(/\r?\n/g, "<br>");
}

function truncateInline(value, maxLength) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function toWikiLink(notePath, label) {
  const safePath = String(notePath ?? "").replace(/\\/g, "/");
  const safeLabel = String(label ?? "").trim() || basenameNoExtension(safePath);
  return `[[${safePath.replace(/\.md$/i, "")}|${safeLabel}]]`;
}

function basenameNoExtension(filePath) {
  return path.posix.basename(String(filePath ?? "").replace(/\\/g, "/"), ".md");
}
