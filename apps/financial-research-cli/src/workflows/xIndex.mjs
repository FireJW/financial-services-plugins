import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const xIndexCommand = {
  name: "x-index",
  script: "x_index.py",
  wrapper: "run_x_index.cmd",
  description: "Run the native X evidence indexing workflow.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    return pushOutputArgs([options.input], options);
  },
  buildSummary(payload) {
    const posts = Array.isArray(payload.x_posts) ? payload.x_posts : [];
    return {
      topic: payload.request?.topic || payload.topic || "",
      post_count: posts.length,
      session_status: payload.session_bootstrap?.status || "",
      fieldtheory_status: payload.fieldtheory_summary?.status || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
    };
  },
  renderSummary(contract) {
    return `Command: x-index\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
