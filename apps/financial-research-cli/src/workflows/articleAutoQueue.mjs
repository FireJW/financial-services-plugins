export const articleAutoQueueCommand = {
  name: "article-auto-queue",
  script: "article_auto_queue.py",
  wrapper: "run_article_auto_queue.cmd",
  description: "Automatically rank candidate topics and push the top items into the article batch workflow.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for article-auto-queue.";
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
    const ranked = Array.isArray(payload.ranked_candidates) ? payload.ranked_candidates : [];
    const topCandidate = ranked[0] || {};
    return {
      candidate_count: payload.candidate_count ?? 0,
      selected_count: payload.selected_count ?? 0,
      publication_readiness: payload.publication_readiness || "",
      top_label: topCandidate.label || "",
      top_selection_status: topCandidate.selection_status || "",
      batch_status: payload.batch_result?.status || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
      report_path: payload.report_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: article-auto-queue",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Candidates / selected: ${contract.summary.candidate_count}/${contract.summary.selected_count}`,
      `Publication readiness: ${contract.summary.publication_readiness || "unknown"}`,
      `Top candidate: ${contract.summary.top_label || "n/a"}`,
      `Top selection: ${contract.summary.top_selection_status || "n/a"}`,
      `Batch status: ${contract.summary.batch_status || "unknown"}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
      `Operator summary: ${contract.summary.operator_summary_status || "unknown"}`,
    ].join("\n");
  },
};
