import { pushOutputArgs } from "./workflowUtils.mjs";

export const articlePublishReuseCommand = {
  name: "article-publish-reuse",
  script: "article_publish_reuse.py",
  wrapper: "run_article_publish_reuse.cmd",
  description: "Rebuild a publish package from an existing publish result and revised article.",
  validateOptions(options) {
    if (!options.basePublishResult) return "Missing required --base-publish-result <path> for article-publish-reuse.";
    if (!options.revisedArticleResult) return "Missing required --revised-article-result <path> for article-publish-reuse.";
    return "";
  },
  buildArgs(options) {
    const args = [
      "--base-publish-result",
      options.basePublishResult,
      "--revised-article-result",
      options.revisedArticleResult,
    ];
    return pushOutputArgs(args, options, { outputDir: true });
  },
  buildSummary(payload) {
    return {
      publication_readiness: payload.publication_readiness || "",
      automatic_acceptance_status: payload.automatic_acceptance?.status || "",
      publish_package_path: payload.publish_package_path || "",
    };
  },
  renderSummary(contract) {
    return `Command: article-publish-reuse\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
