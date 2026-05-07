import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const operatorSummaryCommand = {
  name: "operator-summary",
  script: "operator_summary.py",
  wrapper: "run_operator_summary.cmd",
  description: "Summarize workflow result readiness for an operator.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    return pushOutputArgs([options.input], options);
  },
  buildSummary(payload) {
    return {
      operator_status: payload.operator_status || payload.operator_summary?.operator_status || "",
      operator_recommendation: payload.operator_recommendation || "",
      target: payload.target || "",
      completion_check_status: payload.completion_check?.status || "",
      eval_recommendation: payload.eval_harness?.recommendation || "",
    };
  },
  renderSummary(contract) {
    return `Command: operator-summary\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
