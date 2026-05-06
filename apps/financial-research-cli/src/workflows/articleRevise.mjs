import { pushArticleContentArgs } from "./articleArgs.mjs";

export const articleReviseCommand = {
  name: "article-revise",
  script: "article_revise.py",
  wrapper: "run_article_revise.cmd",
  description: "Revise an article draft from feedback while preserving source integrity.",
  validateOptions(options) {
    if (!options.input) return "Missing required --input <path> for article-revise.";
    if (!options.file) return "Missing required --file <path> for article-revise.";
    return "";
  },
  buildArgs(options) {
    const args = [options.input, "--file", options.file];
    return pushArticleContentArgs(args, options, { includeOutputDir: true });
  },
  buildSummary(payload) {
    return {
      title: payload.revised_article?.title || payload.article_package?.title || "",
      quality_gate: payload.quality_gate || payload.final_stage?.quality_gate || "",
      revision_status: payload.status || "",
      report_path: payload.report_path || "",
    };
  },
  renderSummary(contract) {
    return `Command: article-revise\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
