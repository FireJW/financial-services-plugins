export const wechatDraftPushCommand = {
  name: "wechat-draft-push",
  script: "wechat_push_draft.py",
  wrapper: "run_wechat_push_draft.cmd",
  description: "Push a reviewed publish package into the WeChat draft box.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for wechat-draft-push.";
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
    if (options.author) {
      args.push("--author", options.author);
    }
    if (options.showCoverPic) {
      args.push("--show-cover-pic", String(options.showCoverPic));
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
    if (options.pushBackend) {
      args.push("--push-backend", options.pushBackend);
    }
    if (options.browserSessionStrategy) {
      args.push("--browser-session-strategy", options.browserSessionStrategy);
    }
    if (options.browserDebugEndpoint) {
      args.push("--browser-debug-endpoint", options.browserDebugEndpoint);
    }
    if (options.browserWaitMs) {
      args.push("--browser-wait-ms", String(options.browserWaitMs));
    }
    if (options.browserHomeUrl) {
      args.push("--browser-home-url", options.browserHomeUrl);
    }
    if (options.browserEditorUrl) {
      args.push("--browser-editor-url", options.browserEditorUrl);
    }
    if (options.browserSessionRequired) {
      args.push("--browser-session-required");
    }
    if (options.wechatEnvFile) {
      args.push("--wechat-env-file", options.wechatEnvFile);
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
      push_backend: payload.push_backend || "",
      review_gate_status: payload.review_gate?.status || "",
      publication_readiness: payload.workflow_publication_gate?.publication_readiness || "",
      completion_check_status: payload.completion_check?.status || "",
      operator_status: payload.operator_summary?.operator_status || payload.operator_status || "",
      draft_media_id: payload.draft_result?.media_id || "",
      draft_url: payload.draft_result?.draft_url || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: wechat-draft-push",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Backend: ${contract.summary.push_backend || "unknown"}`,
      `Review gate: ${contract.summary.review_gate_status || "unknown"}`,
      `Publication readiness: ${contract.summary.publication_readiness || "unknown"}`,
      `Completion check: ${contract.summary.completion_check_status || "unknown"}`,
      `Operator status: ${contract.summary.operator_status || "unknown"}`,
      `Draft media_id: ${contract.summary.draft_media_id || "n/a"}`,
    ].join("\n");
  },
};
