import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const completionCheckCommand = {
  name: "completion-check",
  script: "completion_check.py",
  wrapper: "run_completion_check.cmd",
  description: "Check whether a workflow result is complete enough for reuse.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    return pushOutputArgs([options.input], options);
  },
  buildSummary(payload) {
    return {
      completion_status: payload.status || "",
      recommendation: payload.recommendation || "",
      blocker_count: Array.isArray(payload.blockers) ? payload.blockers.length : 0,
      warning_count: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
      target: payload.target || "",
    };
  },
  renderSummary(contract) {
    return `Command: completion-check\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
