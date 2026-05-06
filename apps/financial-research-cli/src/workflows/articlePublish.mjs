import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const articlePublishCommand = {
  name: "article-publish",
  script: "article_publish.py",
  wrapper: "run_article_publish.cmd",
  description: "Build a WeChat-ready publish package from a revised article result.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    const args = [options.input];
    pushOutputArgs(args, options, { outputDir: true });
    if (options.coverImagePath) args.push("--cover-image-path", options.coverImagePath);
    if (options.coverImageUrl) args.push("--cover-image-url", options.coverImageUrl);
    if (options.pushToWechat) args.push("--push-to-wechat");
    return args;
  },
  buildSummary(payload) {
    const publishPackage = payload.publish_package || {};
    return {
      publication_readiness: payload.publication_readiness || "",
      title: publishPackage.title || "",
      push_readiness_status: publishPackage.push_readiness?.status || "",
      publish_package_path: payload.publish_package_path || "",
    };
  },
  renderSummary(contract) {
    return `Command: article-publish\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
