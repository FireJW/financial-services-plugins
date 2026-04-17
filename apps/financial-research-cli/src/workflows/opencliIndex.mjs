export const opencliIndexCommand = {
  name: "opencli-index",
  script: "opencli_bridge.py",
  wrapper: "run_opencli_bridge.cmd",
  description: "Bridge an OpenCLI capture into news-index and emit a stable CLI contract.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for opencli-index.";
    }
    return "";
  },
  buildArgs(options) {
    const args = [options.input];
    if (options.output) {
      args.push("--output", options.output);
    }
    if (options.markdownOutput) {
      args.push("--markdown-output", options.markdownOutput);
    }
    return args;
  },
  buildSummary(payload) {
    const request = payload.request || {};
    const importSummary = payload.import_summary || {};
    const runnerSummary = payload.runner_summary || {};
    const firstObservation = payload.retrieval_result?.observations?.[0] || {};
    return {
      topic: request.topic || "",
      site_profile: request.site_profile || "",
      payload_source: importSummary.payload_source || request.payload_source || "",
      imported_count: importSummary.imported_candidate_count ?? 0,
      duplicate_count: importSummary.skipped_duplicate_count ?? 0,
      artifact_count: importSummary.artifact_count ?? 0,
      runner_status: runnerSummary.status || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
      first_observation_url: firstObservation.url || "",
      completion_check_path: payload.completion_check_path || "",
      operator_summary_path: payload.operator_summary_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: opencli-index",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic: ${contract.summary.topic || "unknown"}`,
      `Site profile: ${contract.summary.site_profile || "unknown"}`,
      `Payload source: ${contract.summary.payload_source || "unknown"}`,
      `Imported candidates: ${contract.summary.imported_count}`,
      `Artifacts: ${contract.summary.artifact_count}`,
      `Runner: ${contract.summary.runner_status || "not_run"}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
      `Operator summary: ${contract.summary.operator_summary_status || "unknown"}`,
      `First observation: ${contract.summary.first_observation_url || "n/a"}`,
    ].join("\n");
  },
};
