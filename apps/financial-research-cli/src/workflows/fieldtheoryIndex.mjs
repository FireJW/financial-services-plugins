import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const fieldtheoryIndexCommand = {
  name: "fieldtheory-index",
  script: "fieldtheory_bookmark_index.py",
  wrapper: "run_fieldtheory_bookmark_index.cmd",
  description: "Index Field Theory bookmark evidence into a workflow result.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    return pushOutputArgs([options.input], options);
  },
  buildSummary(payload) {
    const summary = payload.fieldtheory_summary || {};
    return {
      topic: payload.topic || "",
      lookup_status: summary.status || "",
      matched_count: summary.matched_count ?? 0,
      selected_count: summary.selected_count ?? 0,
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
    };
  },
  renderSummary(contract) {
    return `Command: fieldtheory-index\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
