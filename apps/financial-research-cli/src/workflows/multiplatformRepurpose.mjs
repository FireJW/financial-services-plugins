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
      manifest_path: payload.manifest_path || "",
      report_path: payload.report_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: multiplatform-repurpose",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Run id: ${contract.summary.run_id || "unknown"}`,
      `Source integrity: ${contract.summary.source_integrity_status || "unknown"}`,
      `Platforms: ${contract.summary.platform_count}`,
      `Manifest: ${contract.summary.manifest_path || "n/a"}`,
    ].join("\n");
  },
};
