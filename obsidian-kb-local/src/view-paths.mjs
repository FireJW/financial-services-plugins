import { sanitizeFilename } from "./ingest.mjs";

export function getViewsRoot(machineRoot) {
  return `${machineRoot}/30-views`;
}

export function getSystemViewsDir(machineRoot) {
  return `${getViewsRoot(machineRoot)}/00-System`;
}

export function getGraphInsightsDir(machineRoot) {
  return `${getViewsRoot(machineRoot)}/07-Graph Insights`;
}

export function getNetworkIndexDir(machineRoot) {
  return `${getViewsRoot(machineRoot)}/08-Network Index`;
}

export function getNetworkTraceDir(machineRoot) {
  return `${getViewsRoot(machineRoot)}/09-Network Trace`;
}

export function getTradingPsychologyMentorDir(machineRoot) {
  return `${getViewsRoot(machineRoot)}/10-Trading Psychology Mentor`;
}

export function getTradingPsychologyMentorSessionsDir(machineRoot) {
  return `${getTradingPsychologyMentorDir(machineRoot)}/01-Sessions`;
}

export function getTradingPsychologyMentorTemplatesDir(machineRoot) {
  return `${getTradingPsychologyMentorDir(machineRoot)}/02-Templates`;
}

export function getTradingPsychologyMentorReferenceCasesDir(machineRoot) {
  return `${getTradingPsychologyMentorDir(machineRoot)}/03-Reference Cases`;
}

export function getDashboardPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/00-KB Dashboard.md`;
}

export function getStaleNotesPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/01-Stale Notes.md`;
}

export function getOpenQuestionsPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/02-Open Questions.md`;
}

export function getSourcesByTopicPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/03-Sources by Topic.md`;
}

export function getPoliticalEconomyBookReferencesPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/04-Political Economy Book References.md`;
}

export function getFinanceBookReferencesPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/05-Finance Book References.md`;
}

export function getReferenceMapAuditPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/06-Reference Map Audit.md`;
}

export function getGraphTopicStatusPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/07-Graph Topic Status.md`;
}

export function getCodexThreadCaptureStatusPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/08-Codex Thread Capture Status.md`;
}

export function getCodexThreadRecoveryQueuePath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/09-Codex Thread Recovery Queue.md`;
}

export function getCodexThreadAuditLogPath(machineRoot) {
  return `${getSystemViewsDir(machineRoot)}/10-Codex Thread Audit Log.md`;
}

export function getGraphInsightsPath(machineRoot, topic) {
  return `${getGraphInsightsDir(machineRoot)}/Graph Insights - ${sanitizeFilename(topic)}.md`;
}

export function getGraphInsightsIndexPath(machineRoot) {
  return `${getGraphInsightsDir(machineRoot)}/00-Index.md`;
}

export function getNetworkIndexPath(machineRoot, topic) {
  return `${getNetworkIndexDir(machineRoot)}/Network Index - ${sanitizeFilename(topic)}.md`;
}

export function getNetworkIndexIndexPath(machineRoot) {
  return `${getNetworkIndexDir(machineRoot)}/00-Index.md`;
}

export function getNetworkTracePath(machineRoot, topic) {
  return `${getNetworkTraceDir(machineRoot)}/Network Trace - ${sanitizeFilename(topic)}.md`;
}

export function getNetworkTraceIndexPath(machineRoot) {
  return `${getNetworkTraceDir(machineRoot)}/00-Index.md`;
}

export function getTradingPsychologyMentorSessionPath(machineRoot, title) {
  return `${getTradingPsychologyMentorSessionsDir(machineRoot)}/${sanitizeFilename(title)}.md`;
}

export function getTradingPsychologyMentorTemplatePath(machineRoot, title) {
  return `${getTradingPsychologyMentorTemplatesDir(machineRoot)}/${sanitizeFilename(title)}.md`;
}

export function getTradingPsychologyMentorIndexPath(machineRoot) {
  return `${getTradingPsychologyMentorDir(machineRoot)}/00-Index.md`;
}

export function getTradingPsychologyMentorReferenceCasesIndexPath(machineRoot) {
  return `${getTradingPsychologyMentorReferenceCasesDir(machineRoot)}/00-Index.md`;
}
