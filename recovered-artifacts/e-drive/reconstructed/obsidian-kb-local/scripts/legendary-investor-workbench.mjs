import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { findWikiNotes } from "../src/compile-pipeline.mjs";
import { loadConfig } from "../src/config.mjs";
import {
  callCodexLlmWithFallback,
  formatCodexProviderRouteDetail,
  summarizeLlmProvider
} from "../src/codex-config.mjs";
import {
  analyzeTradingPlan,
  buildRoundtableCommittee,
  buildLegendaryStageFallback as buildLegendaryReasonedStageFallback
} from "../src/legendary-investor-reasoner.mjs";
import { callResponsesApi } from "../src/llm-provider.mjs";
import { buildQuerySynthesisNote, selectRelevantWikiNotes, writeQuerySynthesisNote } from "../src/wiki-query.mjs";
import { rebuildAutomaticLinks } from "../src/link-graph.mjs";
import { readTextFromStdin } from "../src/stdin-text.mjs";
import { refreshWikiViews } from "../src/wiki-views.mjs";
import {
  buildMultiMentorDeltaAnalysis,
  formatMultiMentorDeltaBlock
} from "../src/legendary-investor-doctrines.mjs";
import {
  createSessionState,
  loadSessionState,
  saveSessionState,
  setFact,
  setFacts,
  setConclusion,
  addEvidence,
  setFreshnessRequirement,
  applyFreshnessContract,
  computeDelta,
  buildInteractivityHints,
  formatDeltaSummary,
  formatInteractivityBlock,
  mergeRunResultsIntoSession,
  derivePsychologyConstraints,
  formatPsychologyConstraintsBlock
} from "../src/mentor-session-state.mjs";

const REQUIRED_NOTE_TITLES = [
  "Legendary-Investor-Workbench-v3",
  "Legendary-Investor-Disagreement-Map",
  "Legendary-Investor-Dialogue-Router",
  "Legendary-Investor-Mentor-Query-Console",
  "Hard-Lessons-传奇投资者导师包",
  "Druckenmiller-Critic-Card",
  "Prompt-Template---单导师模式",
  "Prompt-Template---圆桌讨论模式",
  "Prompt-Template---交易复盘导师模式"
];

const STAGES = [
  {
    key: "workbench_v3",
    title: "Workbench v3",
    noteTitles: ["Legendary-Investor-Workbench-v3", "Legendary-Investor-Mentor-Query-Console"],
    instructions: [
      "Classify the situation.",
      "State the default workflow path.",
      "State the best current trade expression.",
      "Use direct practical language."
    ]
  },
  {
    key: "critic_mode",
    title: "Critic Mode",
    noteTitles: ["Druckenmiller-Critic-Card", "Legendary-Investor-Disagreement-Map"],
    instructions: [
      "Write as a hard critic.",
      "Challenge the weakest assumption, the most fragile leg, and the biggest mismatch between conviction and risk.",
      "State what must be cut, delayed, or downgraded."
    ]
  },
  {
    key: "single_mentor",
    title: "单导师",
    noteTitles: [
      "Prompt-Template---单导师模式",
      "Legendary-Investor-Workbench-v3",
      "Legendary-Investor-Mentor-Query-Console"
    ],
    instructions: [
      "Choose the single best mentor for this exact case.",
      "State why that mentor is the best fit.",
      "Then answer in that mentor's voice with trade, sizing, invalidation, and what not to do."
    ]
  },
  {
    key: "roundtable",
    title: "圆桌讨论",
    noteTitles: [
      "Prompt-Template---圆桌讨论模式",
      "Legendary-Investor-Dialogue-Router",
      "Legendary-Investor-Disagreement-Map",
      "Legendary-Investor-Workbench-v3"
    ],
    instructions: [
      "Simulate a roundtable among 3 mentors.",
      "Return structured vote cards for each mentor with vote, confidence, max position, key evidence, and kill switch.",
      "Return a shared committee verdict with default structure, upgrade path, downgrade sequence, and do-not-do actions.",
      "Then return consensus, disagreements, primary plan, backup plan, and what changes the vote.",
      "Keep disagreement only when it changes execution."
    ]
  },
  {
    key: "trade_review",
    title: "交易复盘导师模式",
    noteTitles: [
      "Prompt-Template---交易复盘导师模式",
      "Hard-Lessons-传奇投资者导师包",
      "Legendary-Investor-Disagreement-Map"
    ],
    instructions: [
      "Treat this as a pre-mortem plus post-close review scaffold.",
      "Return the most likely mistake, what to log during execution, what to review after the close, and 5 if-then review rules."
    ]
  },
  {
    key: "final_action_card",
    title: "Final Action Card",
    noteTitles: ["Legendary-Investor-Workbench-v3", "Legendary-Investor-Dialogue-Router"],
    instructions: [
      "Return only a compact action card.",
      "Include Monday pre-open checklist, open conditions, do-not-chase rules, downgrade trigger, and invalidation trigger."
    ]
  }
];

const NOTE_SUMMARY_OVERRIDES = {
  "Legendary-Investor-Workbench-v3":
    "Main scenario console. Routes the user into enterprise selection, position sizing, macro judgment, bubble detection, trade review, and roundtable paths.",
  "Legendary-Investor-Disagreement-Map":
    "Shows where legendary investor lenses disagree, especially on value, cycle, liquidity, convexity, and execution timing.",
  "Legendary-Investor-Dialogue-Router":
    "Routes which mentor combination fits the current problem and what kind of output should come back.",
  "Legendary-Investor-Mentor-Query-Console":
    "Query starter deck for Buffett, Howard Marks, Druckenmiller, Rick Rieder, and workbench action-script flows.",
  "Hard-Lessons-传奇投资者导师包":
    "Execution-heavy mentor pack focused on mistakes, corrections, discipline, and post-trade learning.",
  "Druckenmiller-Critic-Card":
    "Hard critic lens. Focus on asymmetry, conviction versus size, cutting risk fast, and not confusing stubbornness with discipline.",
  "Prompt-Template---单导师模式":
    "Single-mentor template. Choose one best-fit mentor and return direct trade, sizing, invalidation, and what not to do.",
  "Prompt-Template---圆桌讨论模式":
    "Roundtable template. Return consensus, disagreements, primary plan, backup plan, and what changes the vote.",
  "Prompt-Template---交易复盘导师模式":
    "Trade-review template. Return likely mistake, logging fields, post-close review, and if-then anti-error rules."
};

export function parseLegendaryWorkbenchArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  const planText = String(getArg(list, "plan-text") || "").trim();
  const planFile = String(getArg(list, "plan-file") || "").trim();
  const sessionGoal =
    String(getArg(list, "session-goal") || "").trim() ||
    "按 Workbench v3 -> Critic Mode -> 单导师 -> 圆桌讨论 -> 交易复盘导师模式 的顺序，跑完整个实战流程。";
  const topic = String(getArg(list, "topic") || "").trim() || "legendary investor";
  const dryRun = hasFlag(list, "dry-run");
  const execute = hasFlag(list, "execute");
  const continueMode = hasFlag(list, "continue");
  const writeSynthesis = hasFlag(list, "write-synthesis");
  const writeJson = hasFlag(list, "write-json");
  const jsonFile = String(getArg(list, "json-file") || "").trim();
  const skipLinks = hasFlag(list, "skip-links");
  const skipViews = hasFlag(list, "skip-views");
  const noLocalFallback = hasFlag(list, "no-local-fallback");
  const freshSession = hasFlag(list, "fresh-session");
  const playbookOverride = String(getArg(list, "playbook") || "").trim() || "";
  const requestedLimit = Number.parseInt(getArg(list, "limit") || "6", 10);
  const limit = Number.isFinite(requestedLimit)
    ? Math.max(1, Math.min(requestedLimit, 12))
    : 6;
  const requestedTimeout = Number.parseInt(getArg(list, "timeout-ms") || "", 10);
  const timeoutMs = Number.isFinite(requestedTimeout)
    ? Math.max(1, Math.min(requestedTimeout, 30 * 60 * 1000))
    : undefined;

  // Parse --fact key=value pairs (repeatable)
  const facts = parseFactArgs(list);

  if (dryRun && execute) {
    throw buildUsageError("Choose either --dry-run or --execute, not both.");
  }
  if (continueMode && dryRun) {
    throw buildUsageError("--continue cannot be combined with --dry-run.");
  }
  if (writeSynthesis && !execute && !continueMode) {
    throw buildUsageError("--write-synthesis requires --execute.");
  }
  if (writeJson && !execute && !continueMode) {
    throw buildUsageError("--write-json requires --execute or --continue.");
  }
  const VALID_PLAYBOOKS = ["supply_demand_cycle", "event_driven_risk", "valuation_quality", "macro_reflexive"];
  if (playbookOverride && !VALID_PLAYBOOKS.includes(playbookOverride)) {
    throw buildUsageError(`--playbook must be one of: ${VALID_PLAYBOOKS.join(", ")}. Got: "${playbookOverride}"`);
  }

  return {
    planText,
    planFile,
    sessionGoal,
    topic,
    dryRun,
    execute,
    continueMode,
    writeSynthesis,
    writeJson,
    jsonFile,
    skipLinks,
    skipViews,
    noLocalFallback,
    freshSession,
    playbookOverride,
    limit,
    timeoutMs,
    facts
  };
}

export async function executeLegendaryWorkbenchCommand(command, runtime = {}) {
  const writer = runtime.writer || console;
  const config = runtime.config || loadConfig();

  // --continue mode: load prior session, accept new facts, recompute delta only
  if (command.continueMode) {
    return executeLegendaryContinueMode(command, { writer, config, runtime });
  }

  const planInput = await resolvePlanInput(command, runtime);

  // Freshness guard: detect analysis_date in plan input and warn/reject if stale
  const analysisDateMatch = planInput.match(/analysis_date["\s:]*(\d{4}-\d{2}-\d{2})/);
  if (analysisDateMatch) {
    const analysisDate = new Date(analysisDateMatch[1]);
    const now = new Date();
    const calendarDaysOld = Math.floor((now - analysisDate) / (1000 * 60 * 60 * 24));
    if (calendarDaysOld > 5) {
      throw buildUsageError(
        `Shortlist data is too stale for next-day plan. analysis_date=${analysisDateMatch[1]} is ${calendarDaysOld} calendar days old. Rerun shortlist first.`
      );
    }
    if (calendarDaysOld > 3) {
      writer.log(`WARNING: shortlist data may be stale (analysis_date=${analysisDateMatch[1]}, ${calendarDaysOld} calendar days old).`);
    }
  }

  const allWikiNotes = findWikiNotes(config.vaultPath, config.machineRoot, {});
  if (allWikiNotes.length === 0) {
    writer.log("No compiled wiki notes found in the vault scope.");
    return { executed: false, selectedNotes: [], prompt: "" };
  }

  const requiredNotes = collectRequiredNotes(allWikiNotes);
  const retrievalQuery = buildLegendaryWorkbenchQuery(planInput);
  const dynamicNotes = selectRelevantWikiNotes(allWikiNotes, retrievalQuery, {
    topic: command.topic,
    limit: command.limit
  }).map((entry) => entry.note);
  const mergedNotes = mergeNotes(requiredNotes, dynamicNotes);

  writer.log(`Selected ${mergedNotes.length} note(s) for legendary workbench session:`);
  for (const note of mergedNotes) {
    writer.log(`- ${note.relativePath}`);
  }

  if (command.dryRun || !command.execute) {
    const preview = STAGES.map((stage) => {
      const stageNotes = selectStageNotes(mergedNotes, stage.noteTitles);
      return [
        `## ${stage.title}`,
        `- notes: ${stageNotes.map((note) => note.title).join(", ") || "(none)"}`,
        `- instructions: ${stage.instructions.join(" ")}`
      ].join("\n");
    }).join("\n\n");

    writer.log("");
    writer.log(preview);
    writer.log("");
    writer.log("Next step:");
    writer.log(
      "Run node scripts/legendary-investor-workbench.mjs --plan-file <path> --execute --write-synthesis"
    );
    return {
      executed: false,
      selectedNotes: mergedNotes,
      prompt: preview,
      planInput,
      retrievalQuery
    };
  }

  const stageResults = [];
  for (const stage of STAGES) {
    const stageNotes = selectStageNotes(mergedNotes, stage.noteTitles);
    const stagePrompt = buildLegendaryWorkbenchPrompt(
      buildStageTemplate(),
      {
        planInput,
        sessionGoal: command.sessionGoal,
        stageTitle: stage.title,
        stageInstructions: stage.instructions.join("\n- "),
        priorContext: formatPriorStageContext(stageResults),
        noteContext: buildNoteContext(stageNotes)
      }
    );

    writer.log("");
    writer.log(`=== STAGE: ${stage.title} ===`);
    try {
      const resolved = await callCodexLlmWithFallback(stagePrompt, {
        timeoutMs: command.timeoutMs,
        cwd: config.projectRoot,
        callProvider: runtime.callProvider || callResponsesApi
      });

      const provider = resolved.provider;
      const response = resolved.response;
      const output = String(response.outputText || "").trim();

      writer.log(`LLM provider: ${summarizeLlmProvider(provider)}`);
      writer.log(`Provider route: ${formatCodexProviderRouteDetail(provider)}`);
      writer.log(`Provider config: ${resolved.configPath || provider.configPath}`);
      if (Array.isArray(resolved.attempts) && resolved.attempts.length > 1) {
        writer.log("Provider fallback attempts:");
        for (const attempt of resolved.attempts) {
          const status = attempt.ok ? "OK" : "FAIL";
          const detail = attempt.probe?.ok
            ? `response ${attempt.probe.endpoint}`
            : attempt.probe?.error || "no result";
          writer.log(`- [${status}] ${attempt.configPath} :: ${detail}`);
        }
      }
      writer.log("");
      writer.log(output);

      stageResults.push({
        stage,
        notes: stageNotes,
        output,
        provider,
        response,
        resolved,
        mode: "provider"
      });
    } catch (error) {
      if (command.noLocalFallback) {
        throw error;
      }
      writer.log("Provider execution failed. Falling back to local heuristic mode.");
      if (Array.isArray(error.attempts) && error.attempts.length > 0) {
        writer.log("Provider attempts:");
        for (const attempt of error.attempts) {
          const status = attempt.ok ? "OK" : "FAIL";
          const detail = attempt.probe?.ok
            ? `response ${attempt.probe.endpoint}`
            : attempt.probe?.error || "no result";
          writer.log(`- [${status}] ${attempt.configPath} :: ${detail}`);
        }
      }

      const output = buildLegendaryReasonedStageFallback(stage, planInput, stageResults, stageNotes);
      writer.log("");
      writer.log(output);
      stageResults.push({
        stage,
        notes: stageNotes,
        output,
        provider: null,
        response: null,
        resolved: null,
        mode: "local-fallback"
      });
    }
  }

  const answer = [
    buildRunReport(stageResults),
    ...stageResults.map((entry) => `## ${entry.stage.title}\n\n${entry.output}`)
  ].join("\n\n");

  writer.log("");
  writer.log("=== COMBINED ANSWER ===");
  writer.log("");
  writer.log(answer);

  const jsonExport = buildLegendaryWorkbenchJsonExport(planInput, stageResults, {
    sessionGoal: command.sessionGoal,
    retrievalQuery,
    selectedNotes: mergedNotes
  });

  // Session state: load or create, compute delta, save
  const priorState = command.freshSession ? null : loadLegendarySessionState(config.projectRoot);
  if (command.freshSession) {
    writer.log("Fresh session: ignoring prior session state.");
  }
  const sessionState = priorState || initLegendarySessionState();
  const freshnessResult = applyFreshnessContract(sessionState);
  if (freshnessResult.staleCount > 0) {
    writer.log(`Freshness check: ${freshnessResult.staleCount} fact(s) marked stale.`);
  }

  // Cross-chain: load trading-psychology state and derive constraints
  const psychologyState = loadSessionState(config.projectRoot, {
    filename: "mentor-session-state-trading-psychology.json"
  });
  const psychologyConstraints = derivePsychologyConstraints(psychologyState);
  if (psychologyConstraints) {
    writer.log("");
    writer.log("=== PSYCHOLOGY CONSTRAINTS (CROSS-CHAIN) ===");
    writer.log("");
    for (const warning of psychologyConstraints.warnings) {
      writer.log(`  ⚠ ${warning}`);
    }
    writer.log(`  Patterns: ${psychologyConstraints.patterns.join(", ")}`);
    if (psychologyConstraints.confirmLegModifier !== 0) {
      writer.log(`  Confirm leg modifier: ${psychologyConstraints.confirmLegModifier.toFixed(2)}`);
    }
    if (psychologyConstraints.maxPositionCap !== null) {
      writer.log(`  Max position cap: ${psychologyConstraints.maxPositionCap.toFixed(2)}`);
    }
  }

  const summary = analyzeTradingPlan(planInput, { playbookOverride: command.playbookOverride });
  const runResults = extractLegendaryRunResults(summary, stageResults, jsonExport);
  mergeRunResultsIntoSession(sessionState, runResults);

  const delta = computeDelta(sessionState, priorState);
  const interactivityHints = buildInteractivityHints(sessionState, delta);
  sessionState.delta = delta;
  sessionState.interactivity = interactivityHints;

  // Multi-mentor doctrine delta interpretation
  const multiMentorDelta = buildMultiMentorDeltaAnalysis(delta, summary.roundtableMentors || []);

  // Append delta and interactivity to the combined answer
  const deltaBlock = buildLegendaryDeltaBlock(delta);
  const interactivityBlock = buildLegendaryInteractivityBlock(interactivityHints);

  let enrichedAnswer = answer;

  // Inject psychology constraints block if active
  const psychologyBlock = formatPsychologyConstraintsBlock(psychologyConstraints);
  if (psychologyBlock) {
    enrichedAnswer += `\n\n${psychologyBlock}`;
    writer.log("");
    writer.log(psychologyBlock);
  }

  if (deltaBlock) {
    enrichedAnswer += `\n\n${deltaBlock}`;
    writer.log("");
    writer.log("=== DELTA VS PRIOR SESSION ===");
    writer.log("");
    writer.log(deltaBlock);
  }

  // Multi-mentor doctrine interpretation of the delta
  const multiMentorDeltaBlock = formatMultiMentorDeltaBlock(multiMentorDelta);
  if (multiMentorDeltaBlock) {
    enrichedAnswer += `\n\n${multiMentorDeltaBlock}`;
    writer.log("");
    writer.log("=== MULTI-MENTOR DELTA INTERPRETATION ===");
    writer.log("");
    writer.log(multiMentorDeltaBlock);
  }

  if (interactivityBlock) {
    enrichedAnswer += `\n\n${interactivityBlock}`;
    writer.log("");
    writer.log("=== NEXT STEPS ===");
    writer.log("");
    writer.log(interactivityBlock);
  }

  // Add as_of and evidence to JSON export
  jsonExport.asOf = new Date().toISOString();
  jsonExport.evidenceBoard = sessionState.evidenceBoard;
  jsonExport.staleFacts = Object.entries(sessionState.facts)
    .filter(([, fact]) => fact.stale)
    .map(([key]) => key);
  // Stale data warning from analysis_date freshness guard
  if (analysisDateMatch) {
    const calendarDaysOld = Math.floor((new Date() - new Date(analysisDateMatch[1])) / (1000 * 60 * 60 * 24));
    if (calendarDaysOld > 3) {
      jsonExport.stale_data_warning = "shortlist_data_stale";
    }
  }
  jsonExport.unresolvedQuestions = sessionState.unresolvedQuestions;
  jsonExport.delta = delta;
  jsonExport.interactivity = interactivityHints;
  jsonExport.psychologyConstraints = psychologyConstraints;
  jsonExport.multiMentorDelta = multiMentorDelta;

  let jsonWritePath = null;
  if (command.writeJson) {
    jsonWritePath = resolveLegendaryWorkbenchJsonPath(command, config, planInput);
    writeLegendaryWorkbenchJsonExport(jsonWritePath, jsonExport);
    writer.log(`json: ${path.relative(config.projectRoot, jsonWritePath)}`);

    // Save session state alongside JSON export
    const statePath = saveLegendarySessionState(config.projectRoot, sessionState);
    writer.log(`Session state saved: ${statePath}`);
  }

  if (!command.writeSynthesis) {
    return {
      executed: true,
      selectedNotes: mergedNotes,
      planInput,
      retrievalQuery,
      answer: enrichedAnswer,
      stageResults,
      jsonExport,
      jsonWritePath,
      sessionState,
      delta,
      interactivityHints
    };
  }

  const synthesisPreview = buildQuerySynthesisNote(config, {
    query: "Legendary Investor Workbench Session",
    topic: "legendary investor workbench session",
    answer,
    selectedNotes: mergedNotes.map((note) => ({ note, score: 0 })),
    title: buildLegendarySessionTitle(planInput)
  });
  const writeResult = writeQuerySynthesisNote(
    config,
    {
      query: "Legendary Investor Workbench Session",
      topic: "legendary investor workbench session",
      answer,
      selectedNotes: mergedNotes.map((note) => ({ note, score: 0 })),
      title: synthesisPreview.title
    },
    {
      allowFilesystemFallback: true,
      preferCli: true
    }
  );
  writer.log(
    `${writeResult.action}: ${writeResult.path} (mode: ${writeResult.mode}, dedup_key: ${writeResult.dedupKey})`
  );

  let linkResult = null;
  if (!command.skipLinks) {
    linkResult = rebuildAutomaticLinks(config, {
      allowFilesystemFallback: true,
      preferCli: true
    });
    writer.log(
      `Rebuilt automatic links for ${linkResult.updated} note(s) out of ${linkResult.scanned} scanned.`
    );
  }

  let viewResults = [];
  if (!command.skipViews) {
    viewResults = refreshWikiViews(config, {
      allowFilesystemFallback: true,
      preferCli: true
    });
    writer.log(
      `Refreshed wiki views: ${viewResults.map((result) => `${result.path} (${result.mode})`).join(", ")}`
    );
  }

  return {
    executed: true,
    selectedNotes: mergedNotes,
    planInput,
    retrievalQuery,
    answer: enrichedAnswer,
    stageResults,
    jsonExport,
    jsonWritePath,
    writeResult,
    linkResult,
    viewResults,
    sessionState,
    delta,
    interactivityHints
  };
}

export function buildLegendaryWorkbenchPrompt(templateContent, params) {
  return templateContent
    .split("{{PLAN_INPUT}}")
    .join(params.planInput)
    .split("{{SESSION_GOAL}}")
    .join(params.sessionGoal)
    .split("{{STAGE_TITLE}}")
    .join(params.stageTitle || "")
    .split("{{STAGE_INSTRUCTIONS}}")
    .join(params.stageInstructions || "")
    .split("{{PRIOR_CONTEXT}}")
    .join(params.priorContext || "(none yet)")
    .split("{{NOTE_CONTEXT}}")
    .join(params.noteContext || "(no notes)");
}

export function buildLegendaryWorkbenchQuery(planInput) {
  return [
    "Legendary investor workbench v3",
    "critic",
    "single mentor",
    "roundtable",
    "trade review mentor",
    ...extractKeywords(planInput).slice(0, 14)
  ].join(" ");
}

export function collectRequiredNotes(allWikiNotes) {
  return REQUIRED_NOTE_TITLES.map((title) =>
    allWikiNotes.find((note) => stripExtension(note.title) === title)
  ).filter(Boolean);
}

export function buildRunReport(stageResults) {
  const lines = [
    "## Run Report",
    "",
    "| Stage | Mode |",
    "|------|------|"
  ];

  for (const entry of stageResults) {
    const label = entry.mode === "provider" ? "provider" : "local-fallback";
    lines.push(`| ${entry.stage.title} | ${label} |`);
  }

  return lines.join("\n");
}

export function buildLegendaryWorkbenchJsonExport(planInput, stageResults = [], options = {}) {
  const summary = analyzeTradingPlan(planInput, { playbookOverride: options.playbookOverride });
  const primaryRule = summary.stockRules?.[summary.primaryLeg] || null;
  const hedgeRule = summary.stockRules?.[summary.hedgeLeg] || null;
  const confirmRule = summary.stockRules?.[summary.confirmLeg] || null;
  const committee = buildRoundtableCommittee(summary, {
    primaryRule,
    hedgeRule,
    confirmRule
  });

  return {
    schemaVersion: 1,
    exportedAt: new Date().toISOString(),
    sessionGoal: options.sessionGoal || "",
    retrievalQuery: options.retrievalQuery || "",
    planInput,
    summary: {
      scenarioLabel: summary.scenarioLabel,
      singleMentor: summary.singleMentor,
      singleMentorReason: summary.singleMentorReason,
      primaryLeg: summary.primaryLeg,
      hedgeLeg: summary.hedgeLeg,
      confirmLeg: summary.confirmLeg,
      primaryRisk: summary.primaryRisk,
      reversalRisk: summary.reversalRisk,
      invalidTrigger: summary.invalidTrigger,
      changeMindTrigger: summary.changeMindTrigger
    },
    playbook: {
      key: summary.roundtablePlaybookKey,
      label: summary.roundtablePlaybookLabel,
      mentors: summary.roundtableMentors,
      rationale: summary.roundtableRationale
    },
    tradeCards: {
      primary: buildTradeCardExport("primary", summary.primaryLeg, primaryRule),
      hedge: buildTradeCardExport("hedge", summary.hedgeLeg, hedgeRule),
      confirm: buildTradeCardExport("confirm", summary.confirmLeg, confirmRule)
    },
    committee: {
      supportCount: committee.supportCount,
      conditionalCount: committee.conditionalCount,
      opposeCount: committee.opposeCount,
      committeeMaxPosition: committee.committeeMaxPosition,
      consensus: committee.consensus,
      disagreement: committee.disagreement,
      primaryPlan: committee.primaryPlan,
      backupPlan: committee.backupPlan,
      changeMind: committee.changeMind,
      verdict: committee.verdict,
      voteCards: committee.cards
    },
    stages: stageResults.map((entry) => ({
      key: entry.stage.key,
      title: entry.stage.title,
      mode: entry.mode,
      noteTitles: (entry.notes || []).map((note) => note.title),
      output: entry.output
    })),
    selectedNotes: (options.selectedNotes || []).map((note) => ({
      title: note.title,
      relativePath: note.relativePath
    }))
  };
}

export function resolveLegendaryWorkbenchJsonPath(command, config, _planInput) {
  const requested = String(command.jsonFile || "").trim();
  if (requested) {
    return path.resolve(config.projectRoot, requested);
  }
  return path.join(config.projectRoot, "handoff", "legendary-investor-last-run.json");
}

export function writeLegendaryWorkbenchJsonExport(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return filePath;
}

function buildStageTemplate() {
  return [
    "You are running one stage of a legendary investor mentor orchestrator.",
    "",
    "Rules:",
    "1. Use only the trading plan, prior stage context, and selected notes below.",
    "2. Do not use outside knowledge.",
    "3. Do not invent prices, catalysts, business facts, chart facts, or news.",
    "4. Write in Chinese.",
    "5. Return Markdown only.",
    "",
    "## Stage",
    "{{STAGE_TITLE}}",
    "",
    "## Stage Instructions",
    "- {{STAGE_INSTRUCTIONS}}",
    "",
    "## Session Goal",
    "{{SESSION_GOAL}}",
    "",
    "## Trading Plan",
    "{{PLAN_INPUT}}",
    "",
    "## Prior Stage Context",
    "{{PRIOR_CONTEXT}}",
    "",
    "## Selected Notes",
    "{{NOTE_CONTEXT}}"
  ].join("\n");
}

function mergeNotes(requiredNotes, dynamicNotes) {
  const byPath = new Map();
  for (const note of [...requiredNotes, ...dynamicNotes]) {
    if (note?.relativePath) {
      byPath.set(note.relativePath, note);
    }
  }
  return [...byPath.values()];
}

function selectStageNotes(allNotes, requiredTitles) {
  return requiredTitles
    .map((title) => allNotes.find((note) => stripExtension(note.title) === title))
    .filter(Boolean);
}

function buildNoteContext(notes) {
  return notes
    .map((note, index) => {
      const excerpt = buildCompactExcerpt(note, 500);
      return [
        `### Note ${index + 1}: ${note.title}`,
        `- path: ${note.relativePath}`,
        `- wiki_kind: ${note.frontmatter?.wiki_kind || "unknown"}`,
        `- topic: ${note.frontmatter?.topic || ""}`,
        "",
        excerpt
      ].join("\n");
    })
    .join("\n\n");
}

function buildCompactExcerpt(note, maxLength) {
  const title = stripExtension(note?.title || "");
  const preferred = NOTE_SUMMARY_OVERRIDES[title];
  const compact = preferred
    ? preferred
    : sanitizeProviderText(stripFrontmatter(note?.content || "").replace(/\s+/g, " ").trim());
  if (compact.length <= maxLength) {
    return compact;
  }
  return `${compact.slice(0, maxLength).trim()}...`;
}

function sanitizeProviderText(value) {
  return String(value || "")
    .replace(/\[\[([^|\]]+)\|([^\]]+)\]\]/g, "$2")
    .replace(/\[\[([^\]]+)\]\]/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[|]{2,}/g, "|")
    .replace(/\s+/g, " ")
    .trim();
}

function formatPriorStageContext(stageResults) {
  if (!Array.isArray(stageResults) || stageResults.length === 0) {
    return "(none yet)";
  }

  return stageResults
    .map((entry) => {
      const compact = String(entry.output || "").replace(/\s+/g, " ").trim();
      const snippet = compact.length <= 500 ? compact : `${compact.slice(0, 500).trim()}...`;
      return `### ${entry.stage.title}\n${snippet}`;
    })
    .join("\n\n");
}

function buildLegendarySessionTitle(planInput) {
  const firstLine =
    String(planInput || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find(Boolean) || "legendary investor session";
  const compact = firstLine.replace(/^#+\s*/, "").slice(0, 48).trim() || "legendary investor session";
  return `Legendary Investor Session - ${compact}`;
}

async function resolvePlanInput(command, runtime = {}) {
  if (command.planText) {
    return command.planText;
  }
  if (command.planFile) {
    return fs.readFileSync(path.resolve(command.planFile), "utf8").trim();
  }
  if (typeof runtime.readStdin === "function") {
    const text = String(runtime.readStdin() || "").trim();
    if (text) {
      return text;
    }
  }
  if (!process.stdin.isTTY) {
    const reader = runtime.readTextFromStdin || readTextFromStdin;
    const text = String(await reader()).trim();
    if (text) {
      return text;
    }
  }
  throw buildUsageError("Missing plan input. Provide --plan-text, --plan-file, or pipe text through stdin.");
}

function extractKeywords(planInput) {
  const tokens = String(planInput || "")
    .toLowerCase()
    .match(/[\p{L}\p{N}]{2,}/gu);
  if (!tokens) {
    return [];
  }
  return [...new Set(tokens)].filter((token) => !STOPWORDS.has(token));
}

function stripFrontmatter(content) {
  return String(content ?? "").replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "").trim();
}

function stripExtension(value) {
  return String(value || "").replace(/\.md$/i, "");
}

/**
 * --continue mode: load prior session, accept only new facts (--fact args + stdin),
 * recompute delta, output updated interactivity hints without regenerating full stages.
 */
async function executeLegendaryContinueMode(command, { writer, config, runtime = {} }) {
  const priorState = loadLegendarySessionState(config.projectRoot);
  if (!priorState) {
    throw buildUsageError(
      "--continue requires a prior session. Run a full --execute first to create one."
    );
  }

  writer.log("=== CONTINUE MODE (delta-only rerun) ===");
  writer.log("");

  // Collect new facts from --fact args
  const cliFacts = command.facts || {};
  const cliFactCount = Object.keys(cliFacts).length;

  // Collect new facts from stdin (key=value or key: value lines)
  let stdinFacts = {};
  if (!process.stdin.isTTY) {
    const reader = runtime?.readTextFromStdin || readTextFromStdin;
    const stdinText = String(await reader()).trim();
    if (stdinText) {
      stdinFacts = parseFactsFromText(stdinText);
    }
  }
  const stdinFactCount = Object.keys(stdinFacts).length;

  const allNewFacts = { ...stdinFacts, ...cliFacts }; // CLI overrides stdin
  const totalNewFacts = Object.keys(allNewFacts).length;

  if (totalNewFacts === 0) {
    writer.log("No new facts provided. Use --fact key=value or pipe facts through stdin.");
    writer.log("Recomputing delta with freshness contract only.");
  } else {
    writer.log(`New facts: ${totalNewFacts} (${cliFactCount} from --fact, ${stdinFactCount} from stdin)`);
    for (const [key, value] of Object.entries(allNewFacts)) {
      writer.log(`  ${key} = ${value}`);
    }
  }
  writer.log("");

  // Clone prior state as the working session state
  const sessionState = JSON.parse(JSON.stringify(priorState));

  // Apply freshness contract
  const freshnessResult = applyFreshnessContract(sessionState);
  if (freshnessResult.staleCount > 0) {
    writer.log(`Freshness check: ${freshnessResult.staleCount} fact(s) marked stale.`);
  }

  // Merge new facts
  if (totalNewFacts > 0) {
    setFacts(sessionState, allNewFacts);
  }

  // Compute delta
  const delta = computeDelta(sessionState, priorState);
  const interactivityHints = buildInteractivityHints(sessionState, delta);
  sessionState.delta = delta;
  sessionState.interactivity = interactivityHints;

  // Multi-mentor doctrine delta interpretation
  const summary = analyzeTradingPlan(sessionState.rawInputs?.[0] || "");
  const multiMentorDelta = buildMultiMentorDeltaAnalysis(delta, summary.roundtableMentors || []);

  // Cross-chain: load trading-psychology state
  const psychologyState = loadSessionState(config.projectRoot, {
    filename: "mentor-session-state-trading-psychology.json"
  });
  const psychologyConstraints = derivePsychologyConstraints(psychologyState);

  // Output psychology constraints if active
  const psychologyBlock = formatPsychologyConstraintsBlock(psychologyConstraints);
  if (psychologyBlock) {
    writer.log("=== PSYCHOLOGY CONSTRAINTS (CROSS-CHAIN) ===");
    writer.log("");
    writer.log(psychologyBlock);
    writer.log("");
  }

  // Output delta
  const deltaBlock = buildLegendaryDeltaBlock(delta);
  if (deltaBlock) {
    writer.log("=== DELTA VS PRIOR SESSION ===");
    writer.log("");
    writer.log(deltaBlock);
    writer.log("");
  }

  // Output multi-mentor delta interpretation
  const multiMentorDeltaBlock = formatMultiMentorDeltaBlock(multiMentorDelta);
  if (multiMentorDeltaBlock) {
    writer.log("=== MULTI-MENTOR DELTA INTERPRETATION ===");
    writer.log("");
    writer.log(multiMentorDeltaBlock);
    writer.log("");
  }

  // Output interactivity hints
  const interactivityBlock = buildLegendaryInteractivityBlock(interactivityHints);
  if (interactivityBlock) {
    writer.log("=== NEXT STEPS ===");
    writer.log("");
    writer.log(interactivityBlock);
    writer.log("");
  }

  // Save updated session state
  const statePath = saveLegendarySessionState(config.projectRoot, sessionState);
  writer.log(`Session state saved: ${statePath}`);

  // Optionally write JSON export
  let jsonWritePath = null;
  if (command.writeJson) {
    const jsonExport = {
      schemaVersion: 1,
      exportedAt: new Date().toISOString(),
      continueMode: true,
      newFacts: allNewFacts,
      delta,
      interactivity: interactivityHints,
      psychologyConstraints,
      multiMentorDelta,
      staleFacts: Object.entries(sessionState.facts)
        .filter(([, fact]) => fact.stale)
        .map(([key]) => key),
      unresolvedQuestions: sessionState.unresolvedQuestions
    };
    jsonWritePath = resolveLegendaryWorkbenchJsonPath(command, config, "");
    writeLegendaryWorkbenchJsonExport(jsonWritePath, jsonExport);
    writer.log(`json: ${path.relative(config.projectRoot, jsonWritePath)}`);
  }

  return {
    executed: true,
    continueMode: true,
    sessionState,
    delta,
    interactivityHints,
    psychologyConstraints,
    multiMentorDelta,
    jsonWritePath
  };
}

export function printUsage(writer = console.error) {
  writer(
    "Usage: node scripts/legendary-investor-workbench.mjs (--plan-text <text> | --plan-file <path>) [--session-goal <text>] [--topic <topic>] [--limit N] [--timeout-ms N] [--dry-run|--execute|--continue] [--fresh-session] [--playbook <key>] [--fact key=value ...] [--write-synthesis] [--write-json] [--json-file <path>] [--skip-links] [--skip-views] [--no-local-fallback]"
  );
  writer("  --continue   Load prior session, accept new --fact args or stdin facts, recompute delta only (no LLM calls).");
  writer("  --fresh-session  Start with clean session state, ignoring prior run.");
  writer("  --playbook <key>  Override auto-detected playbook (supply_demand_cycle, event_driven_risk, valuation_quality, macro_reflexive).");
  writer("  --fact k=v   Set a fact (repeatable). Also accepts key=value or key: value lines on stdin.");
}

export function reportCliError(error, writer = console.error) {
  const normalizedError = error instanceof Error ? error : new Error(String(error));
  if (normalizedError.code === "USAGE") {
    printUsage(writer);
    writer("");
  }
  writer(normalizedError.message);
  if (Array.isArray(normalizedError.attempts) && normalizedError.attempts.length > 0) {
    writer("");
    writer("Provider attempts:");
    for (const attempt of normalizedError.attempts) {
      const status = attempt.ok ? "OK" : "FAIL";
      const detail = attempt.probe?.ok
        ? `response ${attempt.probe.endpoint}`
        : attempt.probe?.error || "no result";
      writer(`- [${status}] ${attempt.configPath} :: ${detail}`);
    }
  }
}

async function main(args = process.argv.slice(2)) {
  if (hasFlag(args, "help") || hasFlag(args, "h")) {
    printUsage(console.error);
    process.exit(0);
  }

  const command = parseLegendaryWorkbenchArgs(args);
  await executeLegendaryWorkbenchCommand(command);
}

function getArg(args, name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }
  return args[index + 1];
}

function hasFlag(args, name) {
  return args.includes(`--${name}`);
}

function buildUsageError(message) {
  const error = new Error(message);
  error.code = "USAGE";
  return error;
}

/**
 * Parse repeatable --fact key=value arguments from the CLI args list.
 * Returns an object { key: value, ... }.
 */
function parseFactArgs(args) {
  const facts = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--fact" && i + 1 < args.length) {
      const raw = args[i + 1];
      const eqIndex = raw.indexOf("=");
      if (eqIndex > 0) {
        facts[raw.slice(0, eqIndex).trim()] = raw.slice(eqIndex + 1).trim();
      }
      i++; // skip the value
    }
  }
  return facts;
}

/**
 * Parse facts from stdin text. Expects lines of "key=value" or "key: value".
 * Blank lines and lines starting with # are skipped.
 */
function parseFactsFromText(text) {
  const facts = {};
  for (const line of String(text || "").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    // Try key=value first, then key: value
    const eqIndex = trimmed.indexOf("=");
    const colonIndex = trimmed.indexOf(":");
    if (eqIndex > 0) {
      facts[trimmed.slice(0, eqIndex).trim()] = trimmed.slice(eqIndex + 1).trim();
    } else if (colonIndex > 0) {
      facts[trimmed.slice(0, colonIndex).trim()] = trimmed.slice(colonIndex + 1).trim();
    }
  }
  return facts;
}

function isDirectExecution() {
  if (!process.argv[1]) {
    return false;
  }
  try {
    return pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
  } catch {
    return false;
  }
}

const STOPWORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "this",
  "that",
  "will",
  "plan",
  "trade",
  "risk",
  "entry",
  "exit",
  "stop",
  "target",
  "position",
  "交易",
  "计划",
  "主腿",
  "弹性腿",
  "对冲腿",
  "盘前",
  "盘中",
  "复盘"
]);

const LEGENDARY_SESSION_FILENAME = "mentor-session-state-legendary-investor.json";

const LEGENDARY_FRESHNESS_KEYS = [
  "no_agreement_status",
  "brent_overnight",
  "gold_sync",
  "hormuz_status",
  "substantive_progress",
  "auction_gap_status",
  "execution_feasibility_status",
  "volume_confirmation_status"
];

export function loadLegendarySessionState(projectRoot) {
  return loadSessionState(projectRoot, { filename: LEGENDARY_SESSION_FILENAME });
}

export function saveLegendarySessionState(projectRoot, state) {
  return saveSessionState(projectRoot, state, { filename: LEGENDARY_SESSION_FILENAME });
}

export function initLegendarySessionState(params = {}) {
  const state = createSessionState({
    source: "legendary-investor-workbench",
    ...params
  });

  for (const key of LEGENDARY_FRESHNESS_KEYS) {
    setFreshnessRequirement(state, key, { ttlMs: 4 * 60 * 60 * 1000 });
  }

  return state;
}

export function extractLegendaryRunResults(summary, stageResults = [], jsonExport = {}) {
  const results = {
    facts: {},
    conclusions: {},
    unresolvedQuestions: [],
    evidence: {}
  };

  // Extract facts from the plan analysis
  if (summary) {
    if (summary.signals?.noAgreement) {
      results.facts["no_agreement_status"] = "true";
    }
    if (summary.signals?.riskNotReleased) {
      results.facts["risk_not_released"] = "true";
    }
    if (summary.primaryLeg) {
      results.facts["primary_leg"] = summary.primaryLeg;
    }
    if (summary.hedgeLeg) {
      results.facts["hedge_leg"] = summary.hedgeLeg;
    }
    if (summary.confirmLeg) {
      results.facts["confirm_leg"] = summary.confirmLeg;
    }
    results.facts["scenario_label"] = summary.scenarioLabel || "";
    results.facts["single_mentor"] = summary.singleMentor || "";
    results.facts["playbook_key"] = summary.roundtablePlaybookKey || "";
  }

  // Extract conclusions from stage outputs
  for (const entry of stageResults) {
    if (entry.stage.key === "workbench_v3") {
      results.conclusions["workbench_situation"] = (entry.output || "").slice(0, 500);
    }
    if (entry.stage.key === "critic_mode") {
      results.conclusions["critic_assessment"] = (entry.output || "").slice(0, 500);
    }
    if (entry.stage.key === "single_mentor") {
      results.conclusions["single_mentor_advice"] = (entry.output || "").slice(0, 500);
    }
    if (entry.stage.key === "roundtable") {
      results.conclusions["roundtable_verdict"] = (entry.output || "").slice(0, 500);
    }
    if (entry.stage.key === "final_action_card") {
      results.conclusions["action_card"] = (entry.output || "").slice(0, 500);
    }
  }

  // Extract evidence from committee data
  if (jsonExport?.committee) {
    results.evidence["committee_consensus"] = {
      evidence: jsonExport.committee.consensus || "",
      sourceNote: null
    };
    results.evidence["committee_disagreement"] = {
      evidence: jsonExport.committee.disagreement || "",
      sourceNote: null
    };
  }

  // Unresolved: what would change the vote
  if (jsonExport?.committee?.changeMind) {
    results.unresolvedQuestions.push(
      `What would change the committee vote: ${jsonExport.committee.changeMind}`
    );
  }

  // Unresolved: invalidation trigger
  if (summary?.invalidTrigger) {
    results.unresolvedQuestions.push(
      `Invalidation trigger: ${summary.invalidTrigger}`
    );
  }

  return results;
}

export function buildLegendaryDeltaBlock(delta) {
  if (!delta || delta.isFirstRun) {
    return "";
  }
  return `## Delta vs Prior Session\n\n${formatDeltaSummary(delta)}`;
}

export function buildLegendaryInteractivityBlock(hints) {
  if (!hints) {
    return "";
  }
  return formatInteractivityBlock(hints);
}

function buildTradeCardExport(role, leg, rule) {
  return {
    role,
    leg,
    themeEntry: rule?.themeEntry || null,
    confirmEntry: rule?.confirmEntry || null,
    invalidation: rule?.invalidation || null
  };
}

if (isDirectExecution()) {
  try {
    await main();
  } catch (error) {
    reportCliError(error, console.error);
    process.exit(1);
  }
}
