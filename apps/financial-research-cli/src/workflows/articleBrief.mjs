export const articleBriefCommand = {
  name: "article-brief",
  script: "article_brief.py",
  wrapper: "run_article_brief.cmd",
  description: "Build a structured analysis brief from indexed evidence before article drafting.",
  validateOptions(options) {
    if (!options.input) {
      return "Missing required --input <path> for article-brief.";
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
    const brief = payload.analysis_brief || {};
    return {
      topic: payload.source_summary?.topic || payload.request?.topic || "",
      source_kind: payload.source_summary?.source_kind || "",
      canonical_fact_count: Array.isArray(brief.canonical_facts) ? brief.canonical_facts.length : 0,
      not_proven_count: Array.isArray(brief.not_proven) ? brief.not_proven.length : 0,
      story_angle_count: Array.isArray(brief.story_angles) ? brief.story_angles.length : 0,
      supporting_citation_count: Array.isArray(payload.supporting_citations) ? payload.supporting_citations.length : 0,
      recommended_thesis: brief.recommended_thesis || "",
    };
  },
  renderSummary(contract) {
    return [
      "Command: article-brief",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Topic: ${contract.summary.topic || "unknown"}`,
      `Source kind: ${contract.summary.source_kind || "unknown"}`,
      `Canonical facts: ${contract.summary.canonical_fact_count}`,
      `Not proven: ${contract.summary.not_proven_count}`,
      `Story angles: ${contract.summary.story_angle_count}`,
      `Citations: ${contract.summary.supporting_citation_count}`,
    ].join("\n");
  },
};
