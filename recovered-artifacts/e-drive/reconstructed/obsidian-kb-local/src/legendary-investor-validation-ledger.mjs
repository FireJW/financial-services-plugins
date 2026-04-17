/**
 * Validation Ledger — Aggregation for win-rate and failure-mode tracking
 *
 * Reads validation records from a directory and computes:
 *   - win_rate (success / total)
 *   - failure_mode distribution
 *   - rule_delta history
 *   - method improvement trajectory
 *
 * This is the P3 layer — only useful after the daily validation loop
 * has produced multiple real records.
 */

import fs from "node:fs";
import path from "node:path";

/**
 * Load all validation records from a directory.
 * Expects JSON files matching the validation record contract.
 */
export function loadValidationRecords(dirPath, options = {}) {
  const pattern = options.pattern || /legendary-investor-validation-\d{4}-\d{2}-\d{2}.*\.json$/i;
  if (!fs.existsSync(dirPath)) {
    return [];
  }

  return fs.readdirSync(dirPath)
    .filter((name) => pattern.test(name))
    .filter((name) => !name.includes("-last-"))
    .map((name) => {
      try {
        const content = fs.readFileSync(path.join(dirPath, name), "utf8");
        const record = JSON.parse(content);
        if (!record.status || !record.trade_day) return null;
        return { ...record, _filename: name };
      } catch {
        return null;
      }
    })
    .filter(Boolean)
    .sort((a, b) => (a.trade_day || "").localeCompare(b.trade_day || ""));
}

/**
 * Compute aggregated statistics from validation records.
 */
export function aggregateValidationRecords(records) {
  if (!Array.isArray(records) || records.length === 0) {
    return {
      total: 0,
      win_rate: null,
      status_distribution: {},
      failure_modes: [],
      rule_delta_history: [],
      method_trajectory: [],
      recent_streak: null
    };
  }

  const total = records.length;
  const statusCounts = {};
  const failureModeMap = new Map();
  const ruleDeltaHistory = [];
  const methodTrajectory = [];

  for (const record of records) {
    // Status distribution
    const status = record.status || "unknown";
    statusCounts[status] = (statusCounts[status] || 0) + 1;

    // Failure modes from why_wrong
    if (Array.isArray(record.why_wrong)) {
      for (const reason of record.why_wrong) {
        const mode = classifyFailureMode(reason);
        failureModeMap.set(mode, (failureModeMap.get(mode) || 0) + 1);
      }
    }

    // Rule delta history
    if (Array.isArray(record.next_rule_changes) && record.next_rule_changes.length > 0) {
      ruleDeltaHistory.push({
        trade_day: record.trade_day,
        rules: record.next_rule_changes
      });
    }

    // Method trajectory
    if (Array.isArray(record.method_delta) && record.method_delta.length > 0) {
      methodTrajectory.push({
        trade_day: record.trade_day,
        status: record.status,
        deltas: record.method_delta
      });
    }
  }

  const successCount = (statusCounts.success || 0);
  const winRate = total > 0 ? successCount / total : null;

  // Recent streak
  const recentStreak = computeRecentStreak(records);

  // Failure modes sorted by frequency
  const failureModes = [...failureModeMap.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([mode, count]) => ({ mode, count, rate: count / total }));

  return {
    total,
    win_rate: winRate,
    win_rate_label: winRate !== null ? `${(winRate * 100).toFixed(1)}%` : "N/A",
    status_distribution: statusCounts,
    failure_modes: failureModes,
    rule_delta_history: ruleDeltaHistory,
    method_trajectory: methodTrajectory,
    recent_streak: recentStreak
  };
}

/**
 * Render aggregation as human-readable markdown.
 */
export function renderValidationLedger(aggregation) {
  const lines = [
    "# Validation Ledger",
    "",
    `Total Records: ${aggregation.total}`,
    `Win Rate: ${aggregation.win_rate_label || "N/A"}`,
    ""
  ];

  // Status distribution
  lines.push("## Status Distribution");
  for (const [status, count] of Object.entries(aggregation.status_distribution)) {
    const pct = aggregation.total > 0 ? ((count / aggregation.total) * 100).toFixed(1) : "0";
    lines.push(`- ${status}: ${count} (${pct}%)`);
  }
  lines.push("");

  // Recent streak
  if (aggregation.recent_streak) {
    lines.push(`## Recent Streak: ${aggregation.recent_streak.type} x${aggregation.recent_streak.length}`);
    lines.push("");
  }

  // Failure modes
  if (aggregation.failure_modes.length > 0) {
    lines.push("## Top Failure Modes");
    for (const fm of aggregation.failure_modes.slice(0, 5)) {
      lines.push(`- ${fm.mode}: ${fm.count}x (${(fm.rate * 100).toFixed(1)}%)`);
    }
    lines.push("");
  }

  // Rule delta history
  if (aggregation.rule_delta_history.length > 0) {
    lines.push("## Rule Changes Over Time");
    for (const entry of aggregation.rule_delta_history.slice(-5)) {
      lines.push(`### ${entry.trade_day}`);
      for (const rule of entry.rules) {
        lines.push(`- ${rule}`);
      }
    }
    lines.push("");
  }

  // Method trajectory
  if (aggregation.method_trajectory.length > 0) {
    lines.push("## Method Improvement Trajectory");
    for (const entry of aggregation.method_trajectory.slice(-5)) {
      lines.push(`### ${entry.trade_day} (${entry.status})`);
      for (const delta of entry.deltas) {
        lines.push(`- ${delta}`);
      }
    }
    lines.push("");
  }

  return lines.join("\n").trim();
}

// ── Internal Helpers ────────────────────────────────────────────────

function classifyFailureMode(reason) {
  const text = String(reason || "").toLowerCase();

  if (/追高|追价|chased/.test(text)) return "chased_confirm_leg";
  if (/确认|confirmation|纪律/.test(text)) return "confirmation_discipline";
  if (/脑补|story|叙事/.test(text)) return "story_over_fact";
  if (/失效|invalidation/.test(text)) return "ignored_invalidation";
  if (/missing|缺失/.test(text)) return "missing_facts";
  if (/主腿|primary/.test(text)) return "primary_leg_misjudgment";
  if (/对冲|hedge|防守/.test(text)) return "hedge_ineffective";
  if (/价格|price|赔率/.test(text)) return "price_discipline";
  if (/质量|quality/.test(text)) return "quality_misjudgment";

  return "other";
}

function computeRecentStreak(records) {
  if (records.length === 0) return null;

  const last = records[records.length - 1];
  let streakType = last.status === "success" ? "win" : "loss";
  let streakLength = 1;

  for (let i = records.length - 2; i >= 0; i--) {
    const isWin = records[i].status === "success";
    if ((streakType === "win" && isWin) || (streakType === "loss" && !isWin)) {
      streakLength++;
    } else {
      break;
    }
  }

  return { type: streakType, length: streakLength };
}
