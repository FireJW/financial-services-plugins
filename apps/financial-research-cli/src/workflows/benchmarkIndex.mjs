import path from "node:path";

import { repoRoot } from "../config/defaults.mjs";

const benchmarkWorkflowRoot = path.join(
  repoRoot,
  "financial-analysis",
  "skills",
  "decision-journal-publishing",
  "scripts",
);

export const benchmarkIndexCommand = {
  name: "benchmark-index",
  script: "benchmark_index.py",
  wrapper: "run_benchmark_index.cmd",
  pluginId: "financial-analysis",
  skillId: "decision-journal-publishing",
  workflowRoot: benchmarkWorkflowRoot,
  description: "Index and review benchmark article cases from the decision-journal publishing skill.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for benchmark-index.";
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
    const summary = payload.summary || {};
    const firstCase = payload.cases?.[0] || {};
    return {
      loaded_cases: summary.loaded_cases ?? 0,
      considered_cases: summary.considered_cases ?? 0,
      threshold_qualified_cases: summary.threshold_qualified_cases ?? 0,
      exception_qualified_cases: summary.exception_qualified_cases ?? 0,
      candidate_queue_excluded: summary.candidate_queue_excluded ?? 0,
      top_case_id: firstCase.case_id || "",
      top_classification: firstCase.classification || "",
      report_path: payload.report_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: benchmark-index",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Loaded / considered: ${contract.summary.loaded_cases}/${contract.summary.considered_cases}`,
      `Qualified: ${contract.summary.threshold_qualified_cases}`,
      `Qualified exceptions: ${contract.summary.exception_qualified_cases}`,
      `Candidate queue excluded: ${contract.summary.candidate_queue_excluded}`,
      `Top case: ${contract.summary.top_case_id || "n/a"}`,
      `Top classification: ${contract.summary.top_classification || "n/a"}`,
    ].join("\n");
  },
};
