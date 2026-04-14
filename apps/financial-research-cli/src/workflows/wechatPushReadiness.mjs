export const wechatPushReadinessCommand = {
  name: "wechat-push-readiness",
  script: "wechat_push_readiness.py",
  wrapper: "run_wechat_push_readiness.cmd",
  description: "Audit whether a publish package is truly ready for a WeChat push.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for wechat-push-readiness.";
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
    if (options.coverImagePath) {
      args.push("--cover-image-path", options.coverImagePath);
    }
    if (options.coverImageUrl) {
      args.push("--cover-image-url", options.coverImageUrl);
    }
    if (options.humanReviewApproved) {
      args.push("--human-review-approved");
    }
    if (options.humanReviewApprovedBy) {
      args.push("--human-review-approved-by", options.humanReviewApprovedBy);
    }
    if (options.humanReviewNote) {
      args.push("--human-review-note", options.humanReviewNote);
    }
    if (options.wechatEnvFile) {
      args.push("--wechat-env-file", options.wechatEnvFile);
    }
    if (options.validateLiveAuth) {
      args.push("--validate-live-auth");
    }
    if (options.wechatAppId) {
      args.push("--wechat-app-id", options.wechatAppId);
    }
    if (options.wechatAppSecret) {
      args.push("--wechat-app-secret", options.wechatAppSecret);
    }
    if (options.allowInsecureInlineCredentials) {
      args.push("--allow-insecure-inline-credentials");
    }
    if (options.timeoutSeconds) {
      args.push("--timeout-seconds", String(options.timeoutSeconds));
    }
    return args;
  },
  buildSummary(payload) {
    return {
      readiness_level: payload.readiness_level || "",
      ready_for_real_push: Boolean(payload.ready_for_real_push),
      push_readiness_status: payload.push_readiness?.status || "",
      credential_status: payload.credential_check?.status || "",
      live_auth_status: payload.live_auth_check?.status || "",
      publication_readiness: payload.workflow_publication_gate?.publication_readiness || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_status: payload.operator_summary?.operator_status || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: wechat-push-readiness",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Readiness level: ${contract.summary.readiness_level || "unknown"}`,
      `Ready for real push: ${contract.summary.ready_for_real_push ? "true" : "false"}`,
      `Push readiness: ${contract.summary.push_readiness_status || "unknown"}`,
      `Credential status: ${contract.summary.credential_status || "unknown"}`,
      `Live auth: ${contract.summary.live_auth_status || "not_checked"}`,
      `Publication readiness: ${contract.summary.publication_readiness || "unknown"}`,
    ].join("\n");
  },
};
