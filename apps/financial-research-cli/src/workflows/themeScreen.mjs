export const themeScreenCommand = {
  name: "theme-screen",
  script: "hot_topic_discovery.py",
  wrapper: "run_hot_topic_discovery.cmd",
  description: "Run hot-topic discovery as a thin theme-screen surface.",
  validateOptions(options) {
    if (!options.input && !options.topic) {
      return "theme-screen requires either --input <path> or --topic <text>.";
    }
    return "";
  },
  buildArgs(options) {
    const args = [];
    if (options.input) {
      args.push(options.input);
    }
    if (options.output) {
      args.push("--output", options.output);
    }
    if (options.markdownOutput) {
      args.push("--markdown-output", options.markdownOutput);
    }
    if (options.topic) {
      args.push("--topic", options.topic);
    }
    if (options.sources.length > 0) {
      args.push("--sources", ...options.sources);
    }
    if (options.limit) {
      args.push("--limit", String(options.limit));
    }
    if (options.topN) {
      args.push("--top-n", String(options.topN));
    }
    return args;
  },
  buildSummary(payload) {
    return {
      topic_count: Array.isArray(payload.ranked_topics) ? payload.ranked_topics.length : 0,
      top_topic: payload.ranked_topics?.[0]?.title || "",
      top_heat_score: payload.ranked_topics?.[0]?.max_heat_score ?? null,
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: theme-screen",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic count: ${contract.summary.topic_count}`,
      `Top topic: ${contract.summary.top_topic || "n/a"}`,
      `Top heat score: ${contract.summary.top_heat_score ?? "n/a"}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
    ].join("\n");
  },
};
