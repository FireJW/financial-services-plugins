export const agentReachBridgeCommand = {
  name: "agent-reach-bridge",
  script: "agent_reach_bridge.py",
  wrapper: "run_agent_reach_bridge.cmd",
  description: "Bridge Agent Reach discovery results into news-index and emit a stable CLI contract.",
  validateOptions(options) {
    if (!options.input && !options.topic && !options.file) {
      return "agent-reach-bridge requires --input <path>, --topic <text>, or --file <path>.";
    }
    return "";
  },
  buildArgs(options) {
    const args = [];
    if (options.input) {
      args.push(options.input);
    }
    if (options.file) {
      args.push("--file", options.file);
    }
    if (options.topic) {
      args.push("--topic", options.topic);
    }
    if (options.channels.length > 0) {
      args.push("--channels", ...options.channels);
    }
    if (options.pseudoHome) {
      args.push("--pseudo-home", options.pseudoHome);
    }
    if (options.timeoutPerChannel) {
      args.push("--timeout-per-channel", String(options.timeoutPerChannel));
    }
    if (options.maxResultsPerChannel) {
      args.push("--max-results-per-channel", String(options.maxResultsPerChannel));
    }
    if (options.output) {
      args.push("--output", options.output);
    }
    if (options.markdownOutput) {
      args.push("--markdown-output", options.markdownOutput);
    }
    return args;
  },
  buildSummary(payload) {
    const firstObservation = payload.retrieval_result?.observations?.[0] || {};
    const attempted = Array.isArray(payload.channels_attempted) ? payload.channels_attempted : [];
    const succeeded = Array.isArray(payload.channels_succeeded) ? payload.channels_succeeded : [];
    const failed = Array.isArray(payload.channels_failed) ? payload.channels_failed : [];
    return {
      topic: payload.topic || "",
      channels_attempted: attempted.join(","),
      channels_succeeded: succeeded.join(","),
      channel_attempt_count: attempted.length,
      channel_success_count: succeeded.length,
      channel_failure_count: failed.length,
      observations_imported: payload.observations_imported ?? 0,
      observations_skipped_duplicate: payload.observations_skipped_duplicate ?? 0,
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
      first_observation_url: firstObservation.url || "",
      completion_check_path: payload.completion_check_path || "",
      operator_summary_path: payload.operator_summary_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: agent-reach-bridge",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic: ${contract.summary.topic || "unknown"}`,
      `Channels: ${contract.summary.channels_succeeded || "none"} (${contract.summary.channel_success_count}/${contract.summary.channel_attempt_count})`,
      `Failures: ${contract.summary.channel_failure_count}`,
      `Imported observations: ${contract.summary.observations_imported}`,
      `Skipped duplicates: ${contract.summary.observations_skipped_duplicate}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
      `Operator summary: ${contract.summary.operator_summary_status || "unknown"}`,
      `First observation: ${contract.summary.first_observation_url || "n/a"}`,
    ].join("\n");
  },
};
