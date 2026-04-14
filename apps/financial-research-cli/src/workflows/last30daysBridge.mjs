export const last30daysBridgeCommand = {
  name: "last30days-bridge",
  script: "last30days_bridge.py",
  wrapper: "run_last30days_bridge.cmd",
  description: "Bridge a last30days-style discovery result into news-index and emit a stable CLI contract.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for last30days-bridge.";
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
    const firstObservation = payload.retrieval_result?.observations?.[0] || {};
    const batchLabels = Array.isArray(importSummary.batch_labels) ? importSummary.batch_labels : [];
    return {
      topic: request.topic || "",
      raw_item_count: importSummary.raw_item_count ?? 0,
      imported_count: importSummary.imported_candidate_count ?? 0,
      batch_label_count: batchLabels.length,
      blocked_count: importSummary.blocked_count ?? 0,
      with_artifacts: importSummary.with_artifacts ?? 0,
      first_observation_url: firstObservation.url || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: last30days-bridge",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic: ${contract.summary.topic || "unknown"}`,
      `Imported findings: ${contract.summary.imported_count}/${contract.summary.raw_item_count}`,
      `Batches: ${contract.summary.batch_label_count}`,
      `Blocked imports: ${contract.summary.blocked_count}`,
      `Artifacts preserved: ${contract.summary.with_artifacts}`,
      `First observation: ${contract.summary.first_observation_url || "n/a"}`,
    ].join("\n");
  },
};
