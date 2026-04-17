export const morningNoteCommand = {
  name: "morning-note",
  script: "macro_note_workflow.py",
  wrapper: "run_macro_note_workflow.cmd",
  description: "Run the macro-note workflow on an indexed result or source request.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for morning-note.";
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
    if (options.workflowMarkdownOutput) {
      args.push("--workflow-markdown-output", options.workflowMarkdownOutput);
    }
    if (options.outputDir) {
      args.push("--output-dir", options.outputDir);
    }
    return args;
  },
  buildSummary(payload) {
    return {
      topic: payload.topic || "",
      publication_readiness: payload.publication_readiness || "",
      manual_review_status: payload.workflow_publication_gate?.manual_review?.status || "",
      macro_note_result_path: payload.macro_note_stage?.result_path || "",
      operator_summary_path: payload.operator_summary_path || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: morning-note",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic: ${contract.summary.topic || "unknown"}`,
      `Publication readiness: ${contract.summary.publication_readiness || "unknown"}`,
      `Manual review: ${contract.summary.manual_review_status || "unknown"}`,
      `Macro note result: ${contract.summary.macro_note_result_path || "n/a"}`,
    ].join("\n");
  },
};
