import { pushArticleContentArgs } from "./articleArgs.mjs";

export const articleWorkflowCommand = {
  name: "article-workflow",
  script: "article_workflow.py",
  wrapper: "run_article_workflow.cmd",
  description: "Run the end-to-end article workflow from indexed evidence to final draft.",
  validateOptions(options) {
    return options.input ? "" : "Missing required --input <path> for article-workflow.";
  },
  buildArgs(options) {
    return pushArticleContentArgs([options.input], options, { includeOutputDir: true });
  },
  buildSummary(payload) {
    return {
      topic: payload.topic || "",
      source_kind: payload.source_stage?.source_kind || "",
      quality_gate: payload.final_stage?.quality_gate || "",
      publication_readiness: payload.publication_readiness || "",
      final_article_result_path: payload.final_article_result_path || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
    };
  },
  renderSummary(contract) {
    return `Command: article-workflow\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
