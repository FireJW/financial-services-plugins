import path from "node:path";

import { repoRoot } from "../config/defaults.mjs";
import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

const benchmarkWorkflowRoot = path.join(repoRoot, "financial-analysis", "skills", "decision-journal-publishing", "scripts");

export const benchmarkRefreshCommand = {
  name: "benchmark-refresh",
  script: "benchmark_refresh.py",
  wrapper: "run_benchmark_refresh.cmd",
  pluginId: "financial-analysis",
  skillId: "decision-journal-publishing",
  workflowRoot: benchmarkWorkflowRoot,
  description: "Refresh benchmark case library artifacts.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    return pushOutputArgs([options.input], options);
  },
  buildSummary(payload) {
    const summary = payload.summary || {};
    return {
      reviewed_cases_refreshed: summary.reviewed_cases_refreshed ?? 0,
      candidate_cases_refreshed: summary.candidate_cases_refreshed ?? 0,
      candidates_discovered: summary.candidates_discovered ?? 0,
      source_failures: summary.source_failures ?? 0,
      report_path: payload.report_path || "",
    };
  },
  renderSummary(contract) {
    return `Command: benchmark-refresh\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
