import { agentReachDeployCheckCommand } from "./agentReachDeployCheck.mjs";
import { agentReachBridgeCommand } from "./agentReachBridge.mjs";
import { articleAutoQueueCommand } from "./articleAutoQueue.mjs";
import { articleBatchCommand } from "./articleBatch.mjs";
import { articleBriefCommand } from "./articleBrief.mjs";
import { articleDraftCommand } from "./articleDraft.mjs";
import { articleReviseCommand } from "./articleRevise.mjs";
import { articleWorkflowCommand } from "./articleWorkflow.mjs";
import { articlePublishCommand } from "./articlePublish.mjs";
import { articlePublishReuseCommand } from "./articlePublishReuse.mjs";
import { benchmarkIndexCommand } from "./benchmarkIndex.mjs";
import { benchmarkReadinessCommand } from "./benchmarkReadiness.mjs";
import { benchmarkRefreshCommand } from "./benchmarkRefresh.mjs";
import { catalogCommand } from "./catalog.mjs";
import { completionCheckCommand } from "./completionCheck.mjs";
import { earningsUpdateCommand } from "./earningsUpdate.mjs";
import { evalHarnessCommand } from "./evalHarness.mjs";
import { fieldtheoryIndexCommand } from "./fieldtheoryIndex.mjs";
import { horizonBridgeCommand } from "./horizonBridge.mjs";
import { last30daysBridgeCommand } from "./last30daysBridge.mjs";
import { last30daysDeployCheckCommand } from "./last30daysDeployCheck.mjs";
import { morningNoteCommand } from "./morningNote.mjs";
import { multiplatformRepurposeCommand } from "./multiplatformRepurpose.mjs";
import { opencliIndexCommand } from "./opencliIndex.mjs";
import { operatorSummaryCommand } from "./operatorSummary.mjs";
import { pluginCatalogCommand } from "./pluginCatalog.mjs";
import { redditBridgeCommand } from "./redditBridge.mjs";
import { sourceIntakeCommand } from "./sourceIntake.mjs";
import { themeScreenCommand } from "./themeScreen.mjs";
import { wechatDraftPushCommand } from "./wechatDraftPush.mjs";
import { wechatPushReadinessCommand } from "./wechatPushReadiness.mjs";
import { xIndexCommand } from "./xIndex.mjs";

export const COMMANDS = {
  [agentReachDeployCheckCommand.name]: agentReachDeployCheckCommand,
  [agentReachBridgeCommand.name]: agentReachBridgeCommand,
  [articleAutoQueueCommand.name]: articleAutoQueueCommand,
  [articleBatchCommand.name]: articleBatchCommand,
  [articleBriefCommand.name]: articleBriefCommand,
  [articleDraftCommand.name]: articleDraftCommand,
  [articleReviseCommand.name]: articleReviseCommand,
  [articleWorkflowCommand.name]: articleWorkflowCommand,
  [articlePublishCommand.name]: articlePublishCommand,
  [articlePublishReuseCommand.name]: articlePublishReuseCommand,
  [benchmarkIndexCommand.name]: benchmarkIndexCommand,
  [benchmarkReadinessCommand.name]: benchmarkReadinessCommand,
  [benchmarkRefreshCommand.name]: benchmarkRefreshCommand,
  [catalogCommand.name]: catalogCommand,
  [completionCheckCommand.name]: completionCheckCommand,
  [morningNoteCommand.name]: morningNoteCommand,
  [multiplatformRepurposeCommand.name]: multiplatformRepurposeCommand,
  [earningsUpdateCommand.name]: earningsUpdateCommand,
  [evalHarnessCommand.name]: evalHarnessCommand,
  [fieldtheoryIndexCommand.name]: fieldtheoryIndexCommand,
  [horizonBridgeCommand.name]: horizonBridgeCommand,
  [last30daysBridgeCommand.name]: last30daysBridgeCommand,
  [last30daysDeployCheckCommand.name]: last30daysDeployCheckCommand,
  [opencliIndexCommand.name]: opencliIndexCommand,
  [operatorSummaryCommand.name]: operatorSummaryCommand,
  [pluginCatalogCommand.name]: pluginCatalogCommand,
  [redditBridgeCommand.name]: redditBridgeCommand,
  [sourceIntakeCommand.name]: sourceIntakeCommand,
  [themeScreenCommand.name]: themeScreenCommand,
  [wechatDraftPushCommand.name]: wechatDraftPushCommand,
  [wechatPushReadinessCommand.name]: wechatPushReadinessCommand,
  [xIndexCommand.name]: xIndexCommand,
};
