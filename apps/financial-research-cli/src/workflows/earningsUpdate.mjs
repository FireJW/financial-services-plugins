import { pushArticleContentArgs } from "./articleArgs.mjs";

export const earningsUpdateCommand = {
  name: "earnings-update",
  script: "article_workflow.py",
  wrapper: "run_article_workflow.cmd",
  description: "Run the article workflow as a thin earnings-update style surface.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for earnings-update.";
    }
    return "";
  },
  buildArgs(options) {
    const args = [options.input];
    return pushArticleContentArgs(args, options, { includeOutputDir: true });
  },
  buildSummary(payload) {
    return {
      source_kind: payload.source_stage?.source_kind || "",
      publication_readiness: payload.publication_readiness || "",
      quality_gate: payload.final_stage?.quality_gate || "",
      workflow_result_path: payload.final_article_result_path || "",
      operator_summary_path: payload.operator_summary_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: earnings-update",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Source kind: ${contract.summary.source_kind || "unknown"}`,
      `Quality gate: ${contract.summary.quality_gate || "unknown"}`,
      `Publication readiness: ${contract.summary.publication_readiness || "unknown"}`,
      `Workflow result: ${contract.summary.workflow_result_path || "n/a"}`,
    ].join("\n");
  },
};
