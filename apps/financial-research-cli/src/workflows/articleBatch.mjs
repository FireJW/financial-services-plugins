export const articleBatchCommand = {
  name: "article-batch",
  script: "article_batch_workflow.py",
  wrapper: "run_article_batch_workflow.cmd",
  description: "Run the automatic article batch workflow across multiple topics or request files.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for article-batch.";
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
    const items = Array.isArray(payload.items) ? payload.items : [];
    const firstItem = items[0] || {};
    return {
      total_items: payload.total_items ?? 0,
      succeeded_items: payload.succeeded_items ?? 0,
      failed_items: payload.failed_items ?? 0,
      publication_readiness: payload.publication_readiness || "",
      first_label: firstItem.label || "",
      first_quality_gate: firstItem.quality_gate || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_summary_status: payload.operator_summary?.operator_status || "",
      report_path: payload.report_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: article-batch",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Succeeded / total: ${contract.summary.succeeded_items}/${contract.summary.total_items}`,
      `Failed items: ${contract.summary.failed_items}`,
      `Publication readiness: ${contract.summary.publication_readiness || "unknown"}`,
      `First item: ${contract.summary.first_label || "n/a"}`,
      `First quality gate: ${contract.summary.first_quality_gate || "n/a"}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
      `Operator summary: ${contract.summary.operator_summary_status || "unknown"}`,
    ].join("\n");
  },
};
