import { pushArticleContentArgs } from "./articleArgs.mjs";

export const articleDraftCommand = {
  name: "article-draft",
  script: "article_draft.py",
  wrapper: "run_article_draft.cmd",
  description: "Build a reviewable article draft with images and citations from indexed evidence.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for article-draft.";
    }
    return "";
  },
  buildArgs(options) {
    const args = [options.input];
    return pushArticleContentArgs(args, options);
  },
  buildSummary(payload) {
    const articlePackage = payload.article_package || {};
    const selectedImages = Array.isArray(articlePackage.selected_images) ? articlePackage.selected_images : [];
    const citations = Array.isArray(articlePackage.citations) ? articlePackage.citations : [];
    return {
      topic: payload.source_summary?.topic || payload.request?.topic || "",
      source_kind: payload.source_summary?.source_kind || "",
      title: articlePackage.title || "",
      draft_mode: articlePackage.draft_mode || "",
      image_count: selectedImages.length,
      citation_count: citations.length,
      draft_thesis: articlePackage.draft_thesis || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: article-draft",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic: ${contract.summary.topic || "unknown"}`,
      `Source kind: ${contract.summary.source_kind || "unknown"}`,
      `Draft mode: ${contract.summary.draft_mode || "unknown"}`,
      `Images: ${contract.summary.image_count}`,
      `Citations: ${contract.summary.citation_count}`,
      `Title: ${contract.summary.title || "n/a"}`,
    ].join("\n");
  },
};
