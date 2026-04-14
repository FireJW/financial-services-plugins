export const last30daysDeployCheckCommand = {
  name: "last30days-deploy-check",
  script: "last30days_deploy_check.py",
  wrapper: "run_last30days_deploy_check.cmd",
  description: "Inspect a separate last30days deployment and emit a stable CLI contract.",
  validateOptions() {
    return "";
  },
  buildArgs(options) {
    const args = [];
    if (options.input) {
      args.push(options.input);
    }
    if (options.installRoot) {
      args.push("--install-root", options.installRoot);
    }
    if (options.output) {
      args.push("--output", options.output);
    }
    if (options.markdownOutput) {
      args.push("--markdown-output", options.markdownOutput);
    }
    return args;
  },
  buildSummary(payload) {
    const requiredFiles = Array.isArray(payload.required_files) ? payload.required_files : [];
    const requiredGroups = Array.isArray(payload.binary_status?.required_groups)
      ? payload.binary_status.required_groups
      : [];
    const optionalBinaries = Array.isArray(payload.binary_status?.optional) ? payload.binary_status.optional : [];
    return {
      deploy_status: payload.status || "",
      skill_root: payload.skill_root || "",
      required_file_count: requiredFiles.length,
      missing_required_file_count: requiredFiles.filter((item) => !item?.exists).length,
      satisfied_runtime_group_count: requiredGroups.filter((item) => item?.satisfied).length,
      runtime_group_count: requiredGroups.length,
      env_file_present: Boolean(payload.env_status?.env_file?.exists),
      sqlite_candidate_count: Array.isArray(payload.sqlite_candidates) ? payload.sqlite_candidates.length : 0,
      missing_optional_binary_count: optionalBinaries.filter((item) => !item?.available).length,
    };
  },
  renderSummary(contract) {
    return [
      "Command: last30days-deploy-check",
      `Status: ${contract.status}`,
      `Deploy status: ${contract.summary.deploy_status || "unknown"}`,
      `Skill root: ${contract.summary.skill_root || "unknown"}`,
      `Required files: ${contract.summary.required_file_count - contract.summary.missing_required_file_count}/${contract.summary.required_file_count}`,
      `Runtime groups: ${contract.summary.satisfied_runtime_group_count}/${contract.summary.runtime_group_count}`,
      `Env file present: ${contract.summary.env_file_present ? "yes" : "no"}`,
      `SQLite candidates: ${contract.summary.sqlite_candidate_count}`,
      `Missing optional binaries: ${contract.summary.missing_optional_binary_count}`,
    ].join("\n");
  },
};
