import { buildCliContract } from "./output/contracts.mjs";
import { renderExecutionPlan, renderHelp, renderSummary } from "./output/renderers.mjs";
import { buildExecutionPlan, runWorkflowCommand } from "./runtime/headlessSession.mjs";
import { COMMANDS } from "./workflows/index.mjs";

function defaultOptions() {
  return {
    input: "",
    file: "",
    surface: "",
    plugin: "",
    query: "",
    installRoot: "",
    pythonBinary: "",
    output: "",
    markdownOutput: "",
    workflowMarkdownOutput: "",
    outputDir: "",
    topic: "",
    sources: [],
    channels: [],
    limit: "",
    topN: "",
    pseudoHome: "",
    timeoutPerChannel: "",
    maxResultsPerChannel: "",
    basePublishResult: "",
    revisedArticleResult: "",
    titleHint: "",
    subtitleHint: "",
    angle: "",
    tone: "",
    accountName: "",
    author: "",
    articleFramework: "",
    targetLength: "",
    maxImages: "",
    humanSignalRatio: "",
    personalPhrases: [],
    imageStrategy: "",
    draftMode: "",
    headlineHookMode: "",
    headlineHookPrefixes: [],
    pushToWechat: false,
    humanReviewApproved: false,
    humanReviewApprovedBy: "",
    humanReviewNote: "",
    coverImagePath: "",
    coverImageUrl: "",
    wechatEnvFile: "",
    validateLiveAuth: false,
    wechatAppId: "",
    wechatAppSecret: "",
    allowInsecureInlineCredentials: false,
    timeoutSeconds: "",
    showCoverPic: "",
    pushBackend: "",
    browserSessionStrategy: "",
    browserDebugEndpoint: "",
    browserWaitMs: "",
    browserHomeUrl: "",
    browserEditorUrl: "",
    browserSessionRequired: false,
    json: false,
    dryRun: false,
    help: false,
  };
}

export function parseCommonArgs(args) {
  const options = defaultOptions();

  for (let index = 0; index < args.length; index += 1) {
    const token = args[index];
    switch (token) {
      case "--input":
        options.input = args[++index] || "";
        break;
      case "--file":
        options.file = args[++index] || "";
        break;
      case "--surface":
        options.surface = args[++index] || "";
        break;
      case "--plugin":
        options.plugin = args[++index] || "";
        break;
      case "--query":
        options.query = args[++index] || "";
        break;
      case "--install-root":
        options.installRoot = args[++index] || "";
        break;
      case "--python-binary":
        options.pythonBinary = args[++index] || "";
        break;
      case "--output":
        options.output = args[++index] || "";
        break;
      case "--markdown-output":
        options.markdownOutput = args[++index] || "";
        break;
      case "--workflow-markdown-output":
        options.workflowMarkdownOutput = args[++index] || "";
        break;
      case "--output-dir":
        options.outputDir = args[++index] || "";
        break;
      case "--topic":
        options.topic = args[++index] || "";
        break;
      case "--source":
        options.sources.push(args[++index] || "");
        break;
      case "--channel":
        options.channels.push(args[++index] || "");
        break;
      case "--limit":
        options.limit = args[++index] || "";
        break;
      case "--top-n":
        options.topN = args[++index] || "";
        break;
      case "--pseudo-home":
        options.pseudoHome = args[++index] || "";
        break;
      case "--timeout-per-channel":
        options.timeoutPerChannel = args[++index] || "";
        break;
      case "--max-results-per-channel":
        options.maxResultsPerChannel = args[++index] || "";
        break;
      case "--base-publish-result":
        options.basePublishResult = args[++index] || "";
        break;
      case "--revised-article-result":
        options.revisedArticleResult = args[++index] || "";
        break;
      case "--title-hint":
        options.titleHint = args[++index] || "";
        break;
      case "--subtitle-hint":
        options.subtitleHint = args[++index] || "";
        break;
      case "--angle":
        options.angle = args[++index] || "";
        break;
      case "--tone":
        options.tone = args[++index] || "";
        break;
      case "--account-name":
        options.accountName = args[++index] || "";
        break;
      case "--author":
        options.author = args[++index] || "";
        break;
      case "--article-framework":
        options.articleFramework = args[++index] || "";
        break;
      case "--target-length":
        options.targetLength = args[++index] || "";
        break;
      case "--max-images":
        options.maxImages = args[++index] || "";
        break;
      case "--human-signal-ratio":
        options.humanSignalRatio = args[++index] || "";
        break;
      case "--personal-phrase":
        options.personalPhrases.push(args[++index] || "");
        break;
      case "--image-strategy":
        options.imageStrategy = args[++index] || "";
        break;
      case "--draft-mode":
        options.draftMode = args[++index] || "";
        break;
      case "--headline-hook-mode":
        options.headlineHookMode = args[++index] || "";
        break;
      case "--headline-hook-prefix":
        options.headlineHookPrefixes.push(args[++index] || "");
        break;
      case "--push-to-wechat":
        options.pushToWechat = true;
        break;
      case "--human-review-approved":
        options.humanReviewApproved = true;
        break;
      case "--human-review-approved-by":
        options.humanReviewApprovedBy = args[++index] || "";
        break;
      case "--human-review-note":
        options.humanReviewNote = args[++index] || "";
        break;
      case "--cover-image-path":
        options.coverImagePath = args[++index] || "";
        break;
      case "--cover-image-url":
        options.coverImageUrl = args[++index] || "";
        break;
      case "--wechat-env-file":
        options.wechatEnvFile = args[++index] || "";
        break;
      case "--validate-live-auth":
        options.validateLiveAuth = true;
        break;
      case "--wechat-app-id":
        options.wechatAppId = args[++index] || "";
        break;
      case "--wechat-app-secret":
        options.wechatAppSecret = args[++index] || "";
        break;
      case "--allow-insecure-inline-credentials":
        options.allowInsecureInlineCredentials = true;
        break;
      case "--timeout-seconds":
        options.timeoutSeconds = args[++index] || "";
        break;
      case "--show-cover-pic":
        options.showCoverPic = args[++index] || "";
        break;
      case "--push-backend":
        options.pushBackend = args[++index] || "";
        break;
      case "--browser-session-strategy":
        options.browserSessionStrategy = args[++index] || "";
        break;
      case "--browser-debug-endpoint":
        options.browserDebugEndpoint = args[++index] || "";
        break;
      case "--browser-wait-ms":
        options.browserWaitMs = args[++index] || "";
        break;
      case "--browser-home-url":
        options.browserHomeUrl = args[++index] || "";
        break;
      case "--browser-editor-url":
        options.browserEditorUrl = args[++index] || "";
        break;
      case "--browser-session-required":
        options.browserSessionRequired = true;
        break;
      case "--json":
        options.json = true;
        break;
      case "--dry-run":
        options.dryRun = true;
        break;
      case "--help":
      case "-h":
        options.help = true;
        break;
      default:
        return { ok: false, error: `Unknown option: ${token}` };
    }
  }

  return { ok: true, options };
}

export function runCli(argv, { runner = runWorkflowCommand } = {}) {
  if (argv.length === 0) {
    return { exitCode: 0, stdout: renderHelp(COMMANDS), stderr: "" };
  }

  const commandName = argv[0];
  if (commandName === "--help" || commandName === "-h") {
    return { exitCode: 0, stdout: renderHelp(COMMANDS), stderr: "" };
  }

  const command = COMMANDS[commandName];
  if (!command) {
    return {
      exitCode: 1,
      stdout: "",
      stderr: `Unsupported command: ${commandName}\n${renderHelp(COMMANDS)}`,
    };
  }

  const parsed = parseCommonArgs(argv.slice(1));
  if (!parsed.ok) {
    return { exitCode: 1, stdout: "", stderr: `${parsed.error}\n` };
  }

  const { options } = parsed;
  if (options.help) {
    return { exitCode: 0, stdout: renderHelp(COMMANDS), stderr: "" };
  }

  const validationError = command.validateOptions(options);
  if (validationError) {
    return { exitCode: 1, stdout: "", stderr: `${validationError}\n` };
  }

  const plan = buildExecutionPlan(commandName, command, options, COMMANDS);
  if (options.dryRun) {
    return {
      exitCode: 0,
      stdout: renderExecutionPlan(plan, options.json),
      stderr: "",
    };
  }

  if (typeof command.executeLocal === "function") {
    const payload = command.executeLocal({
      commandName,
      command,
      commands: COMMANDS,
      options,
      executionPlan: plan,
    });
    const contract = buildCliContract(commandName, payload, options, plan, command);
    return {
      exitCode: 0,
      stdout: options.json ? `${JSON.stringify(contract, null, 2)}\n` : renderSummary(command, contract),
      stderr: "",
    };
  }

  const runnerResult = runner(commandName, command, options);
  if (!runnerResult.ok) {
    const detail = runnerResult.plan ? `Execution plan: ${JSON.stringify(runnerResult.plan)}\n` : "";
    return {
      exitCode: 1,
      stdout: "",
      stderr: `${runnerResult.error}${runnerResult.error.endsWith("\n") ? "" : "\n"}${detail}`,
    };
  }

  const contract = buildCliContract(commandName, runnerResult.payload, options, runnerResult.plan, command);
  return {
    exitCode: 0,
    stdout: options.json ? `${JSON.stringify(contract, null, 2)}\n` : renderSummary(command, contract),
    stderr: "",
  };
}
