import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { repoRoot } from "./runtime-report-lib.mjs";

export const WORKER_REQUIRED_SECTIONS = [
  "Conclusion",
  "Confirmed",
  "Unconfirmed",
  "Risks",
  "Next Step",
];

export const STRUCTURED_VERIFIER_SCHEMA_VERSION = "structured-verifier-v1";

export const INTENT_REQUIRED_SECTIONS = [
  "User Intent",
  "Hard Constraints",
  "Non-goals",
];

export const COMPACTION_REQUIRED_SECTIONS = [
  ...INTENT_REQUIRED_SECTIONS,
  "Current State",
  "Next Step",
];

export const NOW_TEMPLATE_SECTIONS = [
  {
    title: "Goal",
    key: "goal",
    tokenBudget: 120,
    fallback: "- State the active objective.",
  },
  {
    title: "Current State",
    key: "currentState",
    tokenBudget: 180,
    fallback: "- Summarize the latest implementation state.",
  },
  {
    title: "Confirmed Facts",
    key: "confirmedFacts",
    tokenBudget: 180,
    fallback: "- None.",
  },
  {
    title: "Unresolved Questions",
    key: "unresolvedQuestions",
    tokenBudget: 140,
    fallback: "- None.",
  },
  {
    title: "Next Step",
    key: "nextStep",
    tokenBudget: 80,
    fallback: "- Define the next concrete action.",
  },
  {
    title: "Risks / Invalidation",
    key: "risks",
    tokenBudget: 120,
    fallback: "- None.",
  },
];

export const NOW_REQUIRED_SECTIONS = NOW_TEMPLATE_SECTIONS.map((section) => section.title);

export const TASK_PROFILES_PATH = path.join(
  repoRoot,
  "scripts",
  "runtime",
  "task-profiles.json",
);

const DEFAULT_RUNTIME_PLUGIN_DIRS = [
  "financial-analysis",
  "equity-research",
];

const OPTIONAL_RUNTIME_PLUGIN_DIRS = [
  "investment-banking",
  "private-equity",
  "wealth-management",
];

const PARTNER_RUNTIME_PLUGIN_DIRS = [
  "partner-built/lseg",
  "partner-built/spglobal",
];

const NON_GOAL_PATTERNS = [
  /\bdo not implement\b/i,
  /\bdo not build\b/i,
  /\bout of scope\b/i,
  /\bnon-goal\b/i,
  /\bnon goal\b/i,
  /\bskip\b/i,
  /\bexclude\b/i,
  /\bavoid\b/i,
  /^do not\b/i,
  /^don't\b/i,
  /^不要\b/u,
  /^别\b/u,
  /^先别\b/u,
  /^不做\b/u,
  /^无需\b/u,
  /^不需要\b/u,
  /^不应\b/u,
];

const HARD_CONSTRAINT_PATTERNS = [
  /\bmust\b/i,
  /\bmust not\b/i,
  /\bhighest priority\b/i,
  /\btop priority\b/i,
  /\bhard constraint\b/i,
  /\bdo not break\b/i,
  /\bensure\b/i,
  /\bonly\b/i,
  /\bcannot\b/i,
  /\bnever\b/i,
  /最高优先级/u,
  /铁律/u,
  /必须/u,
  /务必/u,
  /不能/u,
  /不可/u,
  /不要破坏/u,
];

const MULTILINGUAL_NON_GOAL_PATTERNS = [
  /\bdo not start\b/i,
  /\bdo not producti[sz]e\b/i,
  /\bnot in this step\b/i,
  /\bnot part of this step\b/i,
  /^\s*(?:\u4e0d\u8981|\u522b|\u5148\u522b)\s*(?:\u5b9e\u73b0|\u505a|\u5f00\u59cb|\u4ea7\u54c1\u5316|\u5f15\u5165|\u6269\u5c55|\u4e0a)/u,
  /^\s*(?:\u4e0d\u8981|\u522b|\u5148\u522b)\s*(?:\u5728(?:\u8fd9|\u672c)\u4e00\u6b65\s*)?(?:\u5b9e\u73b0|\u505a|\u5f00\u59cb|\u4ea7\u54c1\u5316|\u5f15\u5165|\u6269\u5c55|\u4e0a)/u,
  /^\s*(?:\u4e0d\u7528|\u65e0\u9700|\u4e0d\u9700\u8981|\u6682\u4e0d)/u,
  /\u975e\u76ee\u6807/u,
  /\u4e0d\u5728(?:\u8fd9|\u672c)\u4e00\u6b65/u,
  /\u8df3\u8fc7/u,
  /\u6392\u9664/u,
  /\u907f\u514d/u,
];

const MULTILINGUAL_HARD_CONSTRAINT_PATTERNS = [
  /^\s*only\b/i,
  /\bfile safety\b/i,
  /\bdisk safety\b/i,
  /\bexact as-of date\b/i,
  /\u6700\u9ad8\u4f18\u5148\u7ea7/u,
  /\u9876\u7ea7\u4f18\u5148\u7ea7/u,
  /\u786c\u7ea6\u675f/u,
  /\u94c1\u5f8b/u,
  /\u5fc5\u987b/u,
  /\u52a1\u5fc5/u,
  /\u4e0d\u80fd/u,
  /\u4e0d\u53ef/u,
  /\u786e\u4fdd/u,
  /\u4fdd\u6301/u,
  /\u53ea\u80fd/u,
  /\u6587\u4ef6\u5b89\u5168/u,
  /\u78c1\u76d8\u5b89\u5168/u,
  /^\s*(?:\u4e0d\u8981|\u522b|\u5148\u522b)\s*(?:\u7834\u574f|\u52a8|\u4e71\u5206\u6790|\u8d8a\u754c|\u5220|\u4fee\u6539)/u,
];

export function resolveRepoPath(maybeRelativePath) {
  if (!maybeRelativePath) {
    return null;
  }

  return path.isAbsolute(maybeRelativePath)
    ? path.normalize(maybeRelativePath)
    : path.join(repoRoot, maybeRelativePath);
}

export function parseMarkdownSections(markdown) {
  const normalized = stripUtf8Bom(`${markdown ?? ""}`).replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const sections = [];
  let currentSection = null;

  for (const line of lines) {
    const headingMatch = /^##\s+(.+?)\s*$/.exec(line);
    if (headingMatch) {
      currentSection = {
        title: headingMatch[1].trim(),
        lines: [],
      };
      sections.push(currentSection);
      continue;
    }

    if (currentSection) {
      currentSection.lines.push(line);
    }
  }

  return sections.map((section) => ({
    title: section.title,
    content: section.lines.join("\n").trim(),
  }));
}

export function validateWorkerOutput(markdown) {
  return validateStructuredMarkdown(markdown, WORKER_REQUIRED_SECTIONS, {
    listLikeSections: ["Confirmed", "Unconfirmed", "Risks"],
  });
}

export function validateCompactionSummary(markdown) {
  return validateStructuredMarkdown(markdown, COMPACTION_REQUIRED_SECTIONS, {
    listLikeSections: INTENT_REQUIRED_SECTIONS,
  });
}

export function validateNowMarkdown(markdown) {
  return validateStructuredMarkdown(markdown, NOW_REQUIRED_SECTIONS, {
    listLikeSections: [
      "Confirmed Facts",
      "Unresolved Questions",
      "Risks / Invalidation",
    ],
  });
}

export function buildSessionStateMarkdown(input = {}) {
  const lines = ["# NOW", ""];

  for (const section of NOW_TEMPLATE_SECTIONS) {
    const renderedBody = renderSectionBody(input[section.key], section.fallback);
    const clampedBody = clampSectionBody(renderedBody, section.tokenBudget);
    lines.push(`## ${section.title}`);
    lines.push(`<!-- token-budget: ${section.tokenBudget} -->`);
    lines.push(clampedBody);
    lines.push("");
  }

  return `${lines.join("\n").trimEnd()}\n`;
}

export function buildSessionStatePayload(input = {}) {
  const markdown = buildSessionStateMarkdown(input);

  return {
    markdown,
    validation: validateNowMarkdown(markdown),
    sections: parseMarkdownSections(markdown),
  };
}

export function normalizeIntentMarkdown(rawText) {
  const normalizedText = `${rawText ?? ""}`.trim();
  if (!normalizedText) {
    return buildIntentMarkdownFromSections({
      userIntent: ["Clarify the current user request."],
      hardConstraints: ["None specified."],
      nonGoals: ["None specified."],
    });
  }

  const parsedSections = parseMarkdownSections(normalizedText);
  const sectionMap = new Map(parsedSections.map((section) => [section.title, section.content]));
  const hasStructuredIntent = INTENT_REQUIRED_SECTIONS.every((title) => sectionMap.has(title));

  if (hasStructuredIntent) {
    return buildIntentMarkdownFromSections({
      userIntent: toBulletItems(sectionMap.get("User Intent")),
      hardConstraints: toBulletItems(sectionMap.get("Hard Constraints")),
      nonGoals: toBulletItems(sectionMap.get("Non-goals")),
    });
  }

  return buildIntentMarkdownFromSections(extractIntentSections(normalizedText));
}

export function buildIntentPayload(rawText, options = {}) {
  const intentMarkdown = normalizeIntentMarkdown(rawText);
  const compactSummary = buildCompactionSummaryFromIntent(intentMarkdown, options);

  return {
    intentMarkdown,
    intentValidation: validateStructuredMarkdown(intentMarkdown, INTENT_REQUIRED_SECTIONS, {
      listLikeSections: INTENT_REQUIRED_SECTIONS,
    }),
    compactSummary,
    compactValidation: validateCompactionSummary(compactSummary),
  };
}

export function buildCompactionSummaryFromIntent(intentMarkdown, options = {}) {
  const parsed = parseMarkdownSections(intentMarkdown);
  const sectionMap = new Map(parsed.map((section) => [section.title, section.content]));
  const missingSections = INTENT_REQUIRED_SECTIONS.filter((title) => {
    const content = sectionMap.get(title);
    return !content || !content.trim();
  });

  if (missingSections.length > 0) {
    throw new Error(
      `Intent file is missing required sections: ${missingSections.join(", ")}`,
    );
  }

  const lines = ["# Compact Summary", ""];
  for (const title of INTENT_REQUIRED_SECTIONS) {
    lines.push(`## ${title}`);
    lines.push(sectionMap.get(title));
    lines.push("");
  }
  lines.push("## Current State");
  lines.push(renderSectionBody(options.currentState, "- None."));
  lines.push("");
  lines.push("## Next Step");
  lines.push(renderSectionBody(options.nextStep, "- None."));
  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
}

export function loadTaskProfiles() {
  return JSON.parse(readFileSync(TASK_PROFILES_PATH, "utf8"));
}

export function getTaskProfile(profileName) {
  const config = loadTaskProfiles();
  const profile = config?.profiles?.[profileName];

  if (!profile) {
    const availableProfiles = Object.keys(config?.profiles ?? {}).sort();
    throw new Error(
      `Unknown task profile "${profileName}". Available: ${availableProfiles.join(", ")}`,
    );
  }

  return profile;
}

export function resolveTaskProfile(profileName) {
  const config = loadTaskProfiles();
  const profile = getTaskProfile(profileName);

  return {
    ...profile,
    baseCliArgs: [...(config.baseCliArgs ?? [])],
    contractPath: resolveRepoPath(profile.contractPath),
    checklistPath: resolveRepoPath(profile.checklistPath),
    appendSystemPromptFile: resolveRepoPath(profile.appendSystemPromptFile),
  };
}

export function getRuntimePluginDirs(options = {}) {
  const requestedPluginDirs = options.pluginDirs ?? [];
  const explicitDirs = requestedPluginDirs
    .map((pluginDir) => resolveRepoPath(pluginDir))
    .filter(Boolean);

  const candidateDirs =
    explicitDirs.length > 0
      ? explicitDirs
      : DEFAULT_RUNTIME_PLUGIN_DIRS.map((pluginDir) => resolveRepoPath(pluginDir));

  if (explicitDirs.length === 0 && options.allPlugins) {
    for (const pluginDir of OPTIONAL_RUNTIME_PLUGIN_DIRS) {
      candidateDirs.push(resolveRepoPath(pluginDir));
    }
  }

  if (options.includePartnerBuilt) {
    for (const pluginDir of PARTNER_RUNTIME_PLUGIN_DIRS) {
      candidateDirs.push(resolveRepoPath(pluginDir));
    }
  }

  return dedupeExistingPaths(candidateDirs);
}

export function buildRuntimeCliArgs(profileName, options = {}) {
  const profile = resolveTaskProfile(profileName);
  const pluginDirs = getRuntimePluginDirs(options);
  const forwardedArgs = options.forwardedArgs ?? [];
  const cliArgs = [...profile.baseCliArgs];
  const modelOverride = profile.modelEnv ? process.env[profile.modelEnv] : null;

  for (const pluginDir of pluginDirs) {
    cliArgs.push("--plugin-dir", pluginDir);
  }

  if (profile.appendSystemPromptFile) {
    cliArgs.push("--append-system-prompt-file", profile.appendSystemPromptFile);
  }

  if (
    modelOverride &&
    !forwardedArgs.includes("--model") &&
    !cliArgs.includes("--model")
  ) {
    cliArgs.push("--model", modelOverride);
  }

  cliArgs.push(...(profile.defaultCliArgs ?? []));
  cliArgs.push(...forwardedArgs);

  return {
    profile,
    pluginDirs,
    cliArgs,
  };
}

export function buildTaskProfilePreview(profileName, options = {}) {
  const { profile, pluginDirs, cliArgs } = buildRuntimeCliArgs(profileName, options);

  return {
    profile: {
      name: profile.name,
      description: profile.description ?? profile.purpose ?? "",
      purpose: profile.purpose ?? "",
      modelTier: profile.modelTier,
      modelEnv: profile.modelEnv ?? null,
      thinkingBudget: profile.thinkingBudget,
      maxTurns: profile.maxTurns,
      requiresContract: profile.requiresContract,
      verificationOnly: profile.verificationOnly,
      contractPath: profile.contractPath ?? null,
      checklistPath: profile.checklistPath ?? null,
      notes: profile.notes ?? [],
    },
    invocation: {
      pluginDirs,
      cliArgs,
    },
  };
}

export function buildWorkerPrompt(options) {
  const task = `${options.task ?? ""}`.trim();
  if (!task) {
    throw new Error("Worker prompt requires a task.");
  }

  const lines = [];
  lines.push("You are executing through the runtime worker wrapper.");
  lines.push(
    "Produce the final answer as markdown that follows the required worker contract exactly.",
  );
  lines.push(
    "Keep verified facts in Confirmed, unresolved items in Unconfirmed, and failure modes in Risks.",
  );
  lines.push("Do not add any preamble, commentary, or separator before `## Conclusion`.");
  lines.push("");
  lines.push("## Active Task");
  lines.push(task);
  lines.push("");

  appendOptionalMarkdownSection(lines, "Intent Snapshot", options.intentMarkdown);
  appendOptionalMarkdownSection(lines, "Session Snapshot", options.nowMarkdown);

  for (const contextItem of options.contextItems ?? []) {
    appendOptionalMarkdownSection(lines, contextItem.label, contextItem.content);
  }

  lines.push("## Required Output Shape");
  lines.push("- Return markdown only.");
  lines.push("- Use these headings exactly once and in order:");
  lines.push("- `## Conclusion`");
  lines.push("- `## Confirmed`");
  lines.push("- `## Unconfirmed`");
  lines.push("- `## Risks`");
  lines.push("- `## Next Step`");
  lines.push("- Use bullets for Confirmed, Unconfirmed, and Risks.");
  lines.push("- If a list section has nothing to report, write `- None.`");
  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
}

export function buildVerifierPrompt(options) {
  const originalTask = `${options.originalTask ?? ""}`.trim();
  const workerOutput = `${options.workerOutput ?? ""}`.trim();

  if (!originalTask) {
    throw new Error("Verifier prompt requires the original task.");
  }

  if (!workerOutput) {
    throw new Error("Verifier prompt requires the worker output.");
  }

  const lines = [];
  lines.push("You are executing through the runtime verifier wrapper.");
  lines.push("Review the worker output independently and fail closed.");
  lines.push(
    "Use the appended verification checklist and end with a literal verdict line: `VERDICT: PASS`, `VERDICT: FAIL`, or `VERDICT: PARTIAL`.",
  );
  lines.push(
    "Every substantive check must include `### Check:`, `Command run:`, `Output observed:`, and `Result:` fields.",
  );
  lines.push(
    "Include at least one adversarial probe, such as overclaim detection, missing-risk detection, or invalidation analysis.",
  );
  lines.push("Do not add any preamble before the first `### Check:` block.");
  lines.push("End with the verdict line and nothing after it.");
  lines.push("");
  lines.push("## Original Task");
  lines.push(originalTask);
  lines.push("");
  lines.push("## Worker Output");
  lines.push(workerOutput);
  lines.push("");
  lines.push("## Files Changed");
  lines.push(renderSectionBody(options.filesChanged, "- None provided."));
  lines.push("");
  lines.push("## Approach");
  lines.push(renderSectionBody(options.approach, "- None provided."));
  lines.push("");

  if (options.planPath) {
    lines.push("## Plan Path");
    lines.push(`${options.planPath}`);
    lines.push("");
  }

  appendOptionalMarkdownSection(lines, "Intent Snapshot", options.intentMarkdown);
  appendOptionalMarkdownSection(lines, "Session Snapshot", options.nowMarkdown);

  if (options.preflightReport) {
    appendOptionalMarkdownSection(lines, "Deterministic Preflight", options.preflightReport);
  }

  lines.push("## Minimum Verification Coverage");
  lines.push("- Check whether the worker output satisfies the required worker contract.");
  lines.push("- Check whether Confirmed, Unconfirmed, and Risks are classified honestly.");
  lines.push("- Check whether the conclusion drifts beyond the task that was asked.");
  lines.push("- Include one adversarial probe focused on overclaim, omission, or invalidation.");
  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
}

export function buildStructuredVerifierPrompt(options) {
  const originalTask = `${options.originalTask ?? ""}`.trim();
  const workerOutput = `${options.workerOutput ?? ""}`.trim();

  if (!originalTask) {
    throw new Error("Structured verifier prompt requires the original task.");
  }

  if (!workerOutput) {
    throw new Error("Structured verifier prompt requires the worker output.");
  }

  const lines = [];
  lines.push("You are executing through the runtime structured verifier wrapper.");
  lines.push("Review the worker output independently and fail closed.");
  lines.push("Return JSON only. Do not add markdown fences, commentary, or prose before or after the JSON object.");
  lines.push(`Use schemaVersion = "${STRUCTURED_VERIFIER_SCHEMA_VERSION}".`);
  lines.push("The JSON object must contain:");
  lines.push('- `schemaVersion`: exact string');
  lines.push('- `verdict`: `PASS`, `FAIL`, or `PARTIAL`');
  lines.push('- `hasAdversarialProbe`: boolean');
  lines.push("- `checks`: array of one or more objects");
  lines.push("Each `checks` entry must contain:");
  lines.push('- `title`: string');
  lines.push('- `commandRun`: string');
  lines.push('- `outputObserved`: string');
  lines.push('- `result`: `PASS`, `FAIL`, or `PARTIAL`');
  lines.push('- `isAdversarialProbe`: boolean');
  lines.push("At least one check must be an adversarial probe and `hasAdversarialProbe` must match that fact.");
  lines.push("");
  lines.push("## Original Task");
  lines.push(originalTask);
  lines.push("");
  lines.push("## Worker Output");
  lines.push(workerOutput);
  lines.push("");
  lines.push("## Files Changed");
  lines.push(renderSectionBody(options.filesChanged, "- None provided."));
  lines.push("");
  lines.push("## Approach");
  lines.push(renderSectionBody(options.approach, "- None provided."));
  lines.push("");

  if (options.planPath) {
    lines.push("## Plan Path");
    lines.push(`${options.planPath}`);
    lines.push("");
  }

  appendOptionalMarkdownSection(lines, "Intent Snapshot", options.intentMarkdown);
  appendOptionalMarkdownSection(lines, "Session Snapshot", options.nowMarkdown);

  if (options.preflightReport) {
    appendOptionalMarkdownSection(lines, "Deterministic Preflight", options.preflightReport);
  }

  lines.push("## Minimum Verification Coverage");
  lines.push("- Check whether the worker output satisfies the required worker contract.");
  lines.push("- Check whether Confirmed, Unconfirmed, and Risks are classified honestly.");
  lines.push("- Check whether the conclusion drifts beyond the task that was asked.");
  lines.push("- Include one adversarial probe focused on overclaim, omission, or invalidation.");
  lines.push("");
  lines.push("## JSON Example");
  lines.push("```json");
  lines.push(JSON.stringify({
    schemaVersion: STRUCTURED_VERIFIER_SCHEMA_VERSION,
    verdict: "PASS",
    hasAdversarialProbe: true,
    checks: [
      {
        title: "Contract scan",
        commandRun: "local contract validation",
        outputObserved: "All required sections are present.",
        result: "PASS",
        isAdversarialProbe: false,
      },
      {
        title: "Adversarial overclaim probe",
        commandRun: "compare Confirmed and Unconfirmed certainty levels",
        outputObserved: "No unsupported upgrade from uncertainty to certainty.",
        result: "PASS",
        isAdversarialProbe: true,
      },
    ],
  }, null, 2));
  lines.push("```");
  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
}

export function normalizeWorkerOutputForVerification(markdown) {
  const normalized = stripUtf8Bom(`${markdown ?? ""}`).trim();
  if (!normalized) {
    return "";
  }

  const headingIndex = normalized.indexOf("## Conclusion");
  if (headingIndex === -1) {
    return normalized;
  }

  return `${normalized.slice(headingIndex).trim()}\n`;
}

export function buildRetryPrompt(basePrompt, options = {}) {
  const lines = [`${basePrompt ?? ""}`.trimEnd(), "", "## Retry Directive"];
  lines.push(`- Attempt: ${options.attempt ?? 2}`);
  lines.push(`- Reason: ${options.reason ?? "previous attempt did not satisfy the wrapper contract"}`);

  if (options.kind === "verifier") {
    if (options.structuredOutput) {
      lines.push("- Return JSON only.");
      lines.push("- Do not wrap the JSON in markdown fences.");
      lines.push(`- Use \`schemaVersion: "${STRUCTURED_VERIFIER_SCHEMA_VERSION}"\`.`);
      lines.push("- Include `verdict`, `hasAdversarialProbe`, and a non-empty `checks` array.");
      lines.push("- Each check must include `title`, `commandRun`, `outputObserved`, `result`, and `isAdversarialProbe`.");
      lines.push("- At least one check must be an adversarial probe.");
    } else {
      lines.push("- Start immediately with `### Check:`.");
      lines.push("- Every check must include `**Command run:**`, `**Output observed:**`, and `**Result:**`.");
      lines.push("- Include at least one adversarial probe.");
      lines.push("- End with `VERDICT: PASS`, `VERDICT: FAIL`, or `VERDICT: PARTIAL` and nothing after it.");
    }
  } else {
    lines.push("- Start immediately with `## Conclusion`.");
    lines.push("- Return markdown only.");
    lines.push("- Keep the required worker headings exactly once and in order.");
  }

  if (options.detail) {
    lines.push(`- Previous failure detail: ${options.detail}`);
  }

  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
}

export function getMaxTurnsFromCliArgs(cliArgs = []) {
  const index = getLastFlagIndex(cliArgs, "--max-turns");
  if (index === -1 || index === cliArgs.length - 1) {
    return null;
  }

  const parsed = Number.parseInt(cliArgs[index + 1] ?? "", 10);
  return Number.isFinite(parsed) ? parsed : null;
}

export function bumpMaxTurnsCliArgs(cliArgs = [], nextMaxTurns) {
  const resolvedMaxTurns = Number.isFinite(nextMaxTurns) && nextMaxTurns > 0 ? Math.trunc(nextMaxTurns) : 8;
  const nextArgs = [...cliArgs];
  const index = getLastFlagIndex(nextArgs, "--max-turns");

  if (index === -1) {
    nextArgs.push("--max-turns", `${resolvedMaxTurns}`);
    return nextArgs;
  }

  if (index === nextArgs.length - 1) {
    nextArgs.push(`${resolvedMaxTurns}`);
    return nextArgs;
  }

  nextArgs[index + 1] = `${resolvedMaxTurns}`;
  return nextArgs;
}

function getLastFlagIndex(argv, flagName) {
  for (let index = argv.length - 1; index >= 0; index -= 1) {
    if (argv[index] === flagName) {
      return index;
    }
  }

  return -1;
}

export function parseVerifierOutput(reportText) {
  const normalized = stripVerifierTrailer(reportText);
  const verdictMatch = normalized.match(/^VERDICT:\s+(PASS|FAIL|PARTIAL)\s*$/m);
  const checks = [];
  const missingFields = [];
  const checkRegex = /^### Check:\s*(.+?)\r?\n([\s\S]*?)(?=^### Check:|^VERDICT:|\Z)/gm;
  let match;

  while ((match = checkRegex.exec(normalized)) !== null) {
    const body = match[2].trim();
    const check = {
      title: match[1].trim(),
      body,
      hasCommandRun: /\*\*Command run:\*\*/i.test(body),
      hasOutputObserved: /\*\*Output observed:\*\*/i.test(body),
      hasResult: hasVerifierResultField(body),
      isAdversarialProbe: /(adversarial|probe|boundary|idempotency|orphan|overclaim|invalidat|concurrency)/i.test(
        `${match[1]}\n${body}`,
      ),
    };

    if (!check.hasCommandRun) {
      missingFields.push(`${check.title}: Command run`);
    }
    if (!check.hasOutputObserved) {
      missingFields.push(`${check.title}: Output observed`);
    }
    if (!check.hasResult) {
      missingFields.push(`${check.title}: Result`);
    }

    checks.push(check);
  }

  const hasAdversarialProbe = checks.some((check) => check.isAdversarialProbe);
  const ok =
    Boolean(verdictMatch) &&
    checks.length > 0 &&
    missingFields.length === 0 &&
    hasAdversarialProbe;

  return {
    ok,
    verdict: verdictMatch?.[1] ?? null,
    checks,
    missingFields,
    hasAdversarialProbe,
    raw: normalized,
  };
}

export function validateStructuredVerifierReport(input) {
  const normalized = normalizeStructuredVerifierText(input);
  const missingFields = [];
  const invalidFields = [];
  const checklist = [];
  let parsedReport = null;
  let parseError = null;

  try {
    parsedReport = typeof normalized === "string" ? JSON.parse(normalized) : normalized;
  } catch (error) {
    parseError = error instanceof Error ? error.message : `${error}`;
  }

  const schemaVersionOk =
    !parseError &&
    typeof parsedReport?.schemaVersion === "string" &&
    parsedReport.schemaVersion === STRUCTURED_VERIFIER_SCHEMA_VERSION;
  if (!parseError && !schemaVersionOk) {
    invalidFields.push(
      `schemaVersion: expected "${STRUCTURED_VERIFIER_SCHEMA_VERSION}"`,
    );
  }

  const verdictOk =
    !parseError &&
    typeof parsedReport?.verdict === "string" &&
    ["PASS", "FAIL", "PARTIAL"].includes(parsedReport.verdict);
  if (!parseError && !verdictOk) {
    invalidFields.push("verdict");
  }

  const checks = !parseError && Array.isArray(parsedReport?.checks) ? parsedReport.checks : [];
  const checksPresentOk = !parseError && checks.length > 0;
  if (!parseError && !checksPresentOk) {
    invalidFields.push("checks");
  }

  const derivedAdversarialProbe = checks.some(
    (check) => check && typeof check === "object" && check.isAdversarialProbe === true,
  );
  const hasAdversarialProbeOk =
    !parseError &&
    typeof parsedReport?.hasAdversarialProbe === "boolean" &&
    parsedReport.hasAdversarialProbe === derivedAdversarialProbe &&
    derivedAdversarialProbe;
  if (!parseError && typeof parsedReport?.hasAdversarialProbe !== "boolean") {
    missingFields.push("hasAdversarialProbe");
  } else if (!parseError && !hasAdversarialProbeOk) {
    invalidFields.push("hasAdversarialProbe");
  }

  const checkFieldFailures = [];
  for (const [index, check] of checks.entries()) {
    if (!check || typeof check !== "object") {
      checkFieldFailures.push(`checks[${index}]`);
      continue;
    }

    if (typeof check.title !== "string" || !check.title.trim()) {
      checkFieldFailures.push(`checks[${index}].title`);
    }
    if (typeof check.commandRun !== "string" || !check.commandRun.trim()) {
      checkFieldFailures.push(`checks[${index}].commandRun`);
    }
    if (typeof check.outputObserved !== "string" || !check.outputObserved.trim()) {
      checkFieldFailures.push(`checks[${index}].outputObserved`);
    }
    if (
      typeof check.result !== "string" ||
      !["PASS", "FAIL", "PARTIAL"].includes(check.result)
    ) {
      checkFieldFailures.push(`checks[${index}].result`);
    }
    if (typeof check.isAdversarialProbe !== "boolean") {
      checkFieldFailures.push(`checks[${index}].isAdversarialProbe`);
    }
  }
  invalidFields.push(...checkFieldFailures);

  checklist.push(
    buildChecklistItem(
      "json_parse",
      !parseError,
      !parseError ? "Structured verifier JSON parsed successfully." : `JSON parse error: ${parseError}`,
    ),
  );
  checklist.push(
    buildChecklistItem(
      "schema_version",
      schemaVersionOk,
      schemaVersionOk
        ? `schemaVersion matches ${STRUCTURED_VERIFIER_SCHEMA_VERSION}.`
        : `Expected schemaVersion ${STRUCTURED_VERIFIER_SCHEMA_VERSION}.`,
    ),
  );
  checklist.push(
    buildChecklistItem(
      "verdict",
      verdictOk,
      verdictOk ? "Verdict is present and valid." : "Verdict is missing or invalid.",
    ),
  );
  checklist.push(
    buildChecklistItem(
      "checks",
      checksPresentOk,
      checksPresentOk ? "Structured verifier includes one or more checks." : "Structured verifier checks are missing or empty.",
    ),
  );
  checklist.push(
    buildChecklistItem(
      "check_fields",
      checkFieldFailures.length === 0,
      checkFieldFailures.length === 0
        ? "All structured verifier checks include required fields."
        : `Invalid or missing check fields: ${checkFieldFailures.join(", ")}`,
    ),
  );
  checklist.push(
    buildChecklistItem(
      "adversarial_probe",
      hasAdversarialProbeOk,
      hasAdversarialProbeOk
        ? "Structured verifier includes a consistent adversarial probe."
        : "Structured verifier adversarial probe flag is missing, inconsistent, or false.",
    ),
  );

  const ok = checklist.every((item) => item.ok);

  return {
    ok,
    verdict: verdictOk ? parsedReport.verdict : null,
    schemaVersion:
      typeof parsedReport?.schemaVersion === "string" ? parsedReport.schemaVersion : null,
    parseError,
    checks: checksPresentOk ? checks : [],
    missingFields,
    invalidFields,
    hasAdversarialProbe: derivedAdversarialProbe,
    raw: typeof normalized === "string" ? normalized : JSON.stringify(normalized, null, 2),
    report: parsedReport,
    checklist,
  };
}

export function renderStructuredVerifierMarkdown(reportInput) {
  const validation = validateStructuredVerifierReport(reportInput);
  if (!validation.ok) {
    throw new Error("Cannot render markdown sidecar from an invalid structured verifier report.");
  }

  const lines = [];
  for (const check of validation.checks) {
    lines.push(`### Check: ${check.title}`);
    lines.push(renderStructuredVerifierField("Command run", check.commandRun));
    lines.push("");
    lines.push(renderStructuredVerifierField("Output observed", check.outputObserved));
    lines.push("");
    lines.push(`**Result:** ${check.result}`);
    lines.push("");
    lines.push("---");
    lines.push("");
  }
  lines.push(`VERDICT: ${validation.verdict}`);

  return `${lines.join("\n").trimEnd()}\n`;
}

export function renderDeterministicPreflight(report) {
  const lines = [];
  lines.push(`VERDICT: ${report.verdict}`);
  for (const item of report.checklist) {
    lines.push(`- ${item.name}: ${item.ok ? "PASS" : "FAIL"} - ${item.detail}`);
  }
  return lines.join("\n");
}

function validateStructuredMarkdown(markdown, requiredSections, options = {}) {
  const parsedSections = parseMarkdownSections(markdown);
  const sectionTitles = parsedSections.map((section) => section.title);
  const sectionMap = new Map(parsedSections.map((section) => [section.title, section.content]));
  const missingSections = requiredSections.filter((title) => !sectionMap.has(title));
  const emptySections = requiredSections.filter((title) => {
    const content = sectionMap.get(title);
    return sectionMap.has(title) && !content?.trim();
  });
  const outOfOrderSections = getOutOfOrderSections(sectionTitles, requiredSections);
  const listLikeFailures = (options.listLikeSections ?? []).filter((title) => {
    const content = sectionMap.get(title);
    return content && !hasListLikeContent(content);
  });
  const checklist = [
    buildChecklistItem(
      "required_sections",
      missingSections.length === 0,
      missingSections.length === 0
        ? "All required sections are present."
        : `Missing sections: ${missingSections.join(", ")}`,
    ),
    buildChecklistItem(
      "section_order",
      outOfOrderSections.length === 0,
      outOfOrderSections.length === 0
        ? "Required sections are in the expected order."
        : `Out-of-order sections: ${outOfOrderSections.join(", ")}`,
    ),
    buildChecklistItem(
      "non_empty_sections",
      emptySections.length === 0,
      emptySections.length === 0
        ? "Required sections are non-empty."
        : `Empty sections: ${emptySections.join(", ")}`,
    ),
    buildChecklistItem(
      "list_like_sections",
      listLikeFailures.length === 0,
      listLikeFailures.length === 0
        ? "List-like sections contain bullets or explicit none markers."
        : `Sections must use bullets or explicit none markers: ${listLikeFailures.join(", ")}`,
    ),
  ];

  return {
    verdict: checklist.every((item) => item.ok) ? "PASS" : "FAIL",
    ok: checklist.every((item) => item.ok),
    requiredSections,
    sectionOrder: sectionTitles,
    missingSections,
    emptySections,
    outOfOrderSections,
    listLikeFailures,
    checklist,
  };
}

function extractIntentSections(rawText) {
  const lines = rawText
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => stripIntentBullet(line))
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/^#+\s+/.test(line))
    .filter((line) => !/^user intent brief$/i.test(line));

  const sentences = lines
    .flatMap((line) => splitIntentSentences(line))
    .map((line) => line.trim())
    .filter(Boolean);

  const userIntent = [];
  const hardConstraints = [];
  const nonGoals = [];

  for (const line of sentences) {
    if (INTENT_REQUIRED_SECTIONS.some((title) => title.toLowerCase() === line.toLowerCase())) {
      continue;
    }

    const normalizedLine = normalizeIntentSentence(line);
    if (isHardConstraintIntentLine(normalizedLine)) {
      hardConstraints.push(normalizedLine);
      continue;
    }

    if (isNonGoalIntentLine(normalizedLine)) {
      nonGoals.push(normalizedLine);
      continue;
    }

    userIntent.push(normalizedLine);
  }

  if (userIntent.length === 0 && sentences.length > 0) {
    userIntent.push(normalizeIntentSentence(sentences[0]));
  }

  if (hardConstraints.length === 0) {
    hardConstraints.push("None specified.");
  }

  if (nonGoals.length === 0) {
    nonGoals.push("None specified.");
  }

  return {
    userIntent,
    hardConstraints,
    nonGoals,
  };
}

function hasVerifierResultField(body) {
  const patterns = [
    /\*\*Result:\s*(PASS|FAIL|PARTIAL)\*\*/i,
    /\*\*Result:\*\*\s*(PASS|FAIL|PARTIAL)/i,
    /^Result:\s*(PASS|FAIL|PARTIAL)\s*$/im,
  ];

  return patterns.some((pattern) => pattern.test(body));
}

function stripUtf8Bom(text) {
  return text.replace(/^\uFEFF/, "");
}

function buildIntentMarkdownFromSections(sections) {
  const lines = ["# User Intent Brief", ""];
  lines.push("## User Intent");
  lines.push(renderSectionBody(sections.userIntent, "- Clarify the user request."));
  lines.push("");
  lines.push("## Hard Constraints");
  lines.push(renderSectionBody(sections.hardConstraints, "- None specified."));
  lines.push("");
  lines.push("## Non-goals");
  lines.push(renderSectionBody(sections.nonGoals, "- None specified."));
  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
}

function getOutOfOrderSections(sectionTitles, requiredSections) {
  const positions = requiredSections
    .map((title) => ({
      title,
      position: sectionTitles.indexOf(title),
    }))
    .filter((entry) => entry.position !== -1);

  const outOfOrder = [];
  for (let index = 1; index < positions.length; index += 1) {
    if (positions[index].position < positions[index - 1].position) {
      outOfOrder.push(positions[index].title);
    }
  }

  return outOfOrder;
}

function hasListLikeContent(content) {
  return (
    /^\s*-\s+/m.test(content) ||
    /^\s*\d+\.\s+/m.test(content) ||
    /^\s*None(?:\s+specified)?\.?\s*$/im.test(content) ||
    /^\s*No(?:\s+\w+){0,3}\.\s*$/im.test(content)
  );
}

function buildChecklistItem(name, ok, detail) {
  return { name, ok, detail };
}

function renderSectionBody(value, fallback) {
  if (Array.isArray(value)) {
    const items = value.map((entry) => `${entry}`.trim()).filter(Boolean);
    return items.length > 0 ? items.map((entry) => toBulletLine(entry)).join("\n") : fallback;
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return fallback;
    }
    if (hasListLikeContent(trimmed)) {
      return trimmed;
    }
    return trimmed;
  }

  return fallback;
}

function clampSectionBody(body, tokenBudget) {
  const normalizedBody = `${body ?? ""}`.trim();
  const maxChars = Math.max(120, tokenBudget * 4);

  if (normalizedBody.length <= maxChars) {
    return normalizedBody;
  }

  const lines = normalizedBody.split("\n").map((line) => line.trim()).filter(Boolean);
  if (lines.every((line) => hasListLikeContent(line))) {
    const truncatedLines = [];
    let consumed = 0;
    for (const line of lines) {
      const nextLength = consumed + line.length + 1;
      if (nextLength > maxChars - 24) {
        break;
      }
      truncatedLines.push(line);
      consumed = nextLength;
    }

    if (truncatedLines.length === 0) {
      return `${normalizedBody.slice(0, maxChars - 16).trimEnd()}... [truncated]`;
    }

    if (truncatedLines.join("\n") !== normalizedBody) {
      truncatedLines.push("- Truncated for budget.");
    }
    return truncatedLines.join("\n");
  }

  return `${normalizedBody.slice(0, maxChars - 16).trimEnd()}... [truncated]`;
}

function appendOptionalMarkdownSection(lines, title, content) {
  const trimmedContent = `${content ?? ""}`.trim();
  if (!trimmedContent) {
    return;
  }

  lines.push(`## ${title}`);
  lines.push(trimmedContent);
  lines.push("");
}

function toBulletItems(content) {
  if (!content) {
    return [];
  }

  return content
    .split("\n")
    .map((line) => stripIntentBullet(line).trim())
    .filter(Boolean)
    .map((line) => normalizeIntentSentence(line));
}

function stripIntentBullet(line) {
  return `${line ?? ""}`.replace(/^\s*(?:[-*]|\d+[.)]|\d+、|[（(]\d+[)）])\s+/, "");
}

function normalizeIntentSentence(line) {
  const trimmed = `${line ?? ""}`.trim();
  if (!trimmed) {
    return trimmed;
  }

  if (/[.!?;:。！？；：]$/.test(trimmed)) {
    return trimmed;
  }

  return containsCjkCharacters(trimmed) ? `${trimmed}。` : `${trimmed}.`;
}

function isNonGoalIntentLine(line) {
  return (
    [...MULTILINGUAL_NON_GOAL_PATTERNS, ...NON_GOAL_PATTERNS].some((pattern) => pattern.test(line)) &&
    !/\bdo not break\b/i.test(line) &&
    !/^\s*(?:\u4e0d\u8981|\u522b|\u5148\u522b)\s*\u7834\u574f/u.test(line)
  );
}

function isHardConstraintIntentLine(line) {
  return [...MULTILINGUAL_HARD_CONSTRAINT_PATTERNS, ...HARD_CONSTRAINT_PATTERNS].some((pattern) =>
    pattern.test(line),
  );
}

function containsCjkCharacters(value) {
  return /[\u3400-\u9fff]/u.test(`${value ?? ""}`);
}

function splitIntentSentences(line) {
  return (`${line ?? ""}`.match(/[^.!?;:。！？；：]+(?:[.!?;:。！？；：]+|$)/gu) ?? [])
    .map((part) => part.trim())
    .filter(Boolean);
}

function stripBullet(line) {
  return `${line ?? ""}`.replace(/^\s*(?:[-*]|\d+\.)\s+/, "");
}

function toBulletLine(line) {
  const trimmed = `${line}`.trim();
  return /^[*-]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed) ? trimmed : `- ${trimmed}`;
}

function normalizeSentence(line) {
  const trimmed = `${line ?? ""}`.trim();
  if (!trimmed) {
    return trimmed;
  }

  return /[.!?。；;]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

function isNonGoalLine(line) {
  return NON_GOAL_PATTERNS.some((pattern) => pattern.test(line)) && !/\bdo not break\b/i.test(line);
}

function isHardConstraintLine(line) {
  return HARD_CONSTRAINT_PATTERNS.some((pattern) => pattern.test(line));
}

function dedupeExistingPaths(paths) {
  const seen = new Set();
  const resolved = [];

  for (const candidate of paths) {
    if (!candidate) {
      continue;
    }

    const normalized = path.normalize(candidate);
    if (!existsSync(normalized) || seen.has(normalized)) {
      continue;
    }

    seen.add(normalized);
    resolved.push(normalized);
  }

  return resolved;
}

function stripVerifierTrailer(reportText) {
  return `${reportText ?? ""}`
    .replace(/\r\n/g, "\n")
    .replace(/\n<usage>[\s\S]*$/m, "")
    .trim();
}

function normalizeStructuredVerifierText(input) {
  if (input && typeof input === "object") {
    return input;
  }

  const normalized = stripVerifierTrailer(`${input ?? ""}`).replace(/^\uFEFF/, "");
  const fencedMatch = normalized.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return fencedMatch ? fencedMatch[1].trim() : normalized.trim();
}

function renderStructuredVerifierField(label, value) {
  const normalizedValue = `${value ?? ""}`.trim();
  if (!normalizedValue.includes("\n")) {
    return `**${label}:** ${normalizedValue}`;
  }

  return `**${label}:**\n${normalizedValue}`;
}

function splitIntoSentences(line) {
  return `${line ?? ""}`
    .split(/(?<=[.!?。！？])\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
}
