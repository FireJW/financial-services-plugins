import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const redditBridgeCommand = {
  name: "reddit-bridge",
  script: "reddit_bridge.py",
  wrapper: "run_reddit_bridge.cmd",
  description: "Bridge Reddit exports into the evidence workflow.",
  validateOptions(options) {
    if (!options.input && !options.file) {
      return "reddit-bridge requires --input <path> or --file <path>.";
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
    return pushOutputArgs(args, options);
  },
  buildSummary(payload) {
    const importSummary = payload.import_summary || {};
    return {
      topic: payload.topic || "",
      payload_source: importSummary.payload_source || "",
      imported_count: importSummary.imported_candidate_count ?? 0,
      comment_sample_count: importSummary.comment_sample_count ?? 0,
      operator_review_required_count: importSummary.operator_review_required_count ?? 0,
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
    };
  },
  renderSummary(contract) {
    return `Command: reddit-bridge\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
