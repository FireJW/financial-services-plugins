import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const horizonBridgeCommand = {
  name: "horizon-bridge",
  script: "horizon_bridge.py",
  wrapper: "run_horizon_bridge.cmd",
  description: "Bridge saved Horizon discovery results into news-index as shadow upstream radar signals.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    return pushOutputArgs([options.input], options);
  },
  buildSummary(payload) {
    const request = payload.request || {};
    const importSummary = payload.import_summary || {};
    const firstObservation = payload.retrieval_result?.observations?.[0] || {};
    return {
      topic: request.topic || "",
      payload_source: importSummary.payload_source || "",
      raw_item_count: importSummary.raw_item_count ?? 0,
      imported_count: importSummary.imported_candidate_count ?? 0,
      skipped_invalid_count: importSummary.skipped_invalid_count ?? 0,
      skipped_duplicate_count: importSummary.skipped_duplicate_count ?? 0,
      score_count: importSummary.score_count ?? 0,
      first_observation_origin: firstObservation.origin || "",
      first_observation_channel: firstObservation.channel || "",
      first_observation_access_mode: firstObservation.access_mode || "",
      first_observation_url: firstObservation.url || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
      completion_check_path: payload.completion_check_path || "",
      operator_summary_path: payload.operator_summary_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: horizon-bridge",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic: ${contract.summary.topic || "unknown"}`,
      `Imported findings: ${contract.summary.imported_count}/${contract.summary.raw_item_count}`,
      `Payload source: ${contract.summary.payload_source || "unknown"}`,
      `First observation: ${contract.summary.first_observation_url || "n/a"}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
      `Operator summary: ${contract.summary.operator_summary_status || "unknown"}`,
    ].join("\n");
  },
};
