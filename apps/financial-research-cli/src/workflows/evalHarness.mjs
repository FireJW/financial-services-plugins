export const evalHarnessCommand = {
  name: "eval-harness",
  script: "eval_harness.py",
  wrapper: "run_eval_harness.cmd",
  description: "Run the shared eval scorecard over an existing workflow result.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for eval-harness.";
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
    return {
      workflow_kind: payload.workflow_kind || "",
      recommendation: payload.summary?.recommendation || "",
      average_score: payload.summary?.average_score ?? null,
      finding_count: Array.isArray(payload.findings) ? payload.findings.length : 0,
      target: payload.target || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: eval-harness",
      `Status: ${contract.status}`,
      `Workflow: ${contract.summary.workflow_kind || contract.workflow_kind || "unknown"}`,
      `Recommendation: ${contract.summary.recommendation || "unknown"}`,
      `Average score: ${contract.summary.average_score ?? "n/a"}`,
      `Findings: ${contract.summary.finding_count}`,
      `Target: ${contract.summary.target || "n/a"}`,
    ].join("\n");
  },
};
