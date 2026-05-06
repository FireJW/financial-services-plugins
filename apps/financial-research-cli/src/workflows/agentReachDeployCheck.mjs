import { pushOutputArgs, requireInput } from "./workflowUtils.mjs";

export const agentReachDeployCheckCommand = {
  name: "agent-reach-deploy-check",
  script: "agent_reach_deploy_check.py",
  wrapper: "run_agent_reach_deploy_check.cmd",
  description: "Check local Agent Reach bridge prerequisites.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    const args = [options.input];
    if (options.installRoot) args.push("--install-root", options.installRoot);
    if (options.pseudoHome) args.push("--pseudo-home", options.pseudoHome);
    if (options.pythonBinary) args.push("--python-binary", options.pythonBinary);
    return pushOutputArgs(args, options);
  },
  buildSummary(payload) {
    const binaries = payload.binaries || {};
    const channels = payload.channels || {};
    return {
      deploy_status: payload.status || "",
      core_channels_ready: Boolean(payload.core_channels_ready),
      channel_ok_count: Object.values(channels).filter((value) => value === "ok" || value === true).length,
      missing_binary_count: Object.values(binaries).filter((value) => value !== "ok" && value !== true).length,
    };
  },
  renderSummary(contract) {
    return `Command: agent-reach-deploy-check\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
