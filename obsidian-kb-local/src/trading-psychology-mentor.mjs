import {
  getTradingPsychologyMentorSessionPath,
  getTradingPsychologyMentorTemplatePath
} from "./view-paths.mjs";

const TEMPLATES = {
  premarket: {
    id: "premarket",
    label: "盘前模板",
    body: "## 盘前检查\n\n- 今日主要风险是什么？\n- 什么条件下不交易？"
  },
  intraday: {
    id: "intraday",
    label: "盘中模板",
    body: "## 盘中检查\n\n- 当前动作是否符合原计划？\n- 是否正在追涨或报复？"
  },
  postmarket: {
    id: "postmarket",
    label: "盘后模板",
    body: "## 盘后复盘\n\n- 今日偏离点是什么？\n- 明日修正：写下一个可执行动作。"
  }
};

export function resolveTradingPsychologyMentorTemplate(template = "intraday") {
  return TEMPLATES[String(template || "intraday").toLowerCase()] || TEMPLATES.intraday;
}

export function buildTradingPsychologyMentorPrompt(templateContent, params = {}) {
  return String(templateContent || "")
    .replaceAll("{{QUERY}}", String(params.query || ""))
    .replaceAll("{{TOPIC}}", String(params.topic || ""))
    .replaceAll("{{JOURNAL_CONTEXT}}", String(params.journalContext || ""))
    .replaceAll("{{NOTE_CONTEXT}}", String(params.noteContext || ""));
}

export function buildTradingPsychologyMentorSessionNote(config, params = {}) {
  const query = String(params.query || "trading psychology session").trim();
  const templateLabel = String(params.templateLabel || "盘中模板");
  const title = `Trading Psychology Session - ${query.slice(0, 48)}`;
  const content = [
    `# ${title}`,
    "",
    "## Query",
    "",
    query,
    "",
    "## Template",
    "",
    templateLabel,
    "",
    "## Journal Context",
    "",
    String(params.journalContext || "(none)"),
    "",
    buildExecutionContext(params),
    "## Mentor Response",
    "",
    String(params.answer || "(no answer)"),
    "",
    "## Selected Notes",
    "",
    formatSelectedNotes(params.selectedNotes || []),
    ""
  ]
    .filter((line) => line !== null)
    .join("\n");

  return {
    path: getTradingPsychologyMentorSessionPath(config.machineRoot, title),
    content
  };
}

export function buildTradingPsychologyTemplateNote(config, templateName = "intraday") {
  const template = resolveTradingPsychologyMentorTemplate(templateName);
  return {
    path: getTradingPsychologyMentorTemplatePath(
      config.machineRoot,
      `Trading Psychology Template - ${template.label}`
    ),
    content: [`# Trading Psychology Template - ${template.label}`, "", template.body, ""].join("\n")
  };
}

export function buildTradingPsychologyMentorFallbackResponse(params = {}) {
  const text = `${params.query || ""}\n${params.journalContext || ""}`;
  const earlyStarter = /底仓|确认未完全|过早加仓|提前加仓/.test(text);
  if (earlyStarter) {
    return [
      "## Pattern",
      "",
      "- FOMO: present but mild.",
      "- 过早加仓冲动：核心风险是把底仓变成确认前的加仓。",
      "",
      "## What You Did Well",
      "",
      "- 底仓规模小，说明你保留了等待确认的空间。",
      "",
      "## Next Drill",
      "",
      "- 写下加仓触发条件；触发前只允许观察。"
    ].join("\n");
  }

  return [
    "## Pattern",
    "",
    "- FOMO: chasing strength before the plan confirms.",
    "- 报复性交易：亏损和不甘心驱动追回，而不是新信号。",
    "",
    "## What You Did Well",
    "",
    "- You noticed the emotional loop instead of normalizing it.",
    "",
    "## Next Drill",
    "",
    "- After a stop, wait one full setup cycle before re-entry."
  ].join("\n");
}

function buildExecutionContext(params) {
  if (!params.responseMode && !params.providerRoute && !params.providerEndpoint && !params.fallbackReason) {
    return null;
  }

  return [
    "## Execution Context",
    "",
    `- Response mode: ${params.responseMode || "(unknown)"}`,
    `- Provider route: ${params.providerRoute || "(unknown)"}`,
    `- Provider endpoint: ${params.providerEndpoint || "(unknown)"}`,
    params.fallbackReason ? `- Fallback reason: ${params.fallbackReason}` : "",
    ""
  ].join("\n");
}

function formatSelectedNotes(selectedNotes) {
  if (!Array.isArray(selectedNotes) || selectedNotes.length === 0) {
    return "- No selected notes.";
  }
  return selectedNotes
    .map((entry) => {
      const note = entry.note || entry;
      return `- ${note.title || note.relativePath || "(untitled)"}`;
    })
    .join("\n");
}
