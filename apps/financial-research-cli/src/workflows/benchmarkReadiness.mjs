import path from "node:path";

import { repoRoot } from "../config/defaults.mjs";

const benchmarkWorkflowRoot = path.join(
  repoRoot,
  "financial-analysis",
  "skills",
  "decision-journal-publishing",
  "scripts",
);

export const benchmarkReadinessCommand = {
  name: "benchmark-readiness",
  script: "benchmark_readiness.py",
  wrapper: "run_benchmark_readiness.cmd",
  pluginId: "financial-analysis",
  skillId: "decision-journal-publishing",
  workflowRoot: benchmarkWorkflowRoot,
  description: "Audit whether a benchmark refresh request is safe for recurring execution.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for benchmark-readiness.";
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
    return {
      readiness_level: payload.readiness_level || "",
      ready_for_daily_refresh: Boolean(payload.ready_for_daily_refresh),
      blocker_count: Array.isArray(payload.blockers) ? payload.blockers.length : 0,
      warning_count: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
      reviewed_cases: summary.reviewed_cases ?? 0,
      candidate_cases: summary.candidate_cases ?? 0,
      enabled_seed_sources: summary.enabled_seed_sources ?? 0,
    };
  },
  renderSummary(contract) {
    return [
      "Command: benchmark-readiness",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Readiness level: ${contract.summary.readiness_level || "unknown"}`,
      `Ready for daily refresh: ${contract.summary.ready_for_daily_refresh ? "yes" : "no"}`,
      `Blockers: ${contract.summary.blocker_count}`,
      `Warnings: ${contract.summary.warning_count}`,
      `Reviewed / candidates: ${contract.summary.reviewed_cases}/${contract.summary.candidate_cases}`,
      `Enabled seeds: ${contract.summary.enabled_seed_sources}`,
    ].join("\n");
  },
};
