import { requireInput } from "./workflowUtils.mjs";

export const multiplatformRepurposeCommand = {
  name: "multiplatform-repurpose",
  script: "multiplatform_repurpose.py",
  wrapper: "run_multiplatform_repurpose.cmd",
  description: "Repurpose one source article into platform-native review packages.",
  validateOptions(options) {
    return requireInput(this.name, options);
  },
  buildArgs(options) {
    const args = [options.input];
    if (options.outputDir) {
      args.push("--output-dir", options.outputDir);
    }
    if (options.output) {
      args.push("--output", options.output);
    }
    return args;
  },
  buildSummary(payload) {
    const platforms = payload.platforms || {};
    return {
      run_id: payload.run_id || "",
      source_integrity_status: payload.source_integrity?.status || "",
      platform_count: Object.keys(platforms).length,
      completion_check_status: payload.completion_check?.status || "",
      ready_platform_count: payload.completion_check?.summary?.ready_platform_count ?? 0,
      blocker_count: payload.completion_check?.summary?.blocker_count ?? 0,
      warning_count: payload.completion_check?.summary?.warning_count ?? 0,
      manifest_path: payload.manifest_path || "",
      report_path: payload.report_path || "",
      completion_check_path: payload.completion_check_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: multiplatform-repurpose",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Run id: ${contract.summary.run_id || "unknown"}`,
      `Source integrity: ${contract.summary.source_integrity_status || "unknown"}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
      `Platforms: ${contract.summary.platform_count}`,
      `Ready platforms: ${contract.summary.ready_platform_count}/${contract.summary.platform_count}`,
      `Blockers: ${contract.summary.blocker_count}`,
      `Warnings: ${contract.summary.warning_count}`,
      `Manifest: ${contract.summary.manifest_path || "n/a"}`,
    ].join("\n");
  },
};
