#!/usr/bin/env python3
"""
Article workflow regression test suite.

This file aggregates the article-workflow test modules that were split from
the original monolithic test_article_workflow.py (151KB, corrupted during
the 2026-04 repo recovery).

Modules:
    test_article_workflow_normalize   — normalize_workflow_request
    test_article_workflow_draft       — build_draft_payload, build_brief_payload, build_revision_template
    test_article_workflow_summary     — summarize_* helpers
    test_article_workflow_revision    — red team, rewrite, rebuild, reorder, persist feedback
    test_article_workflow_integration — run_article_workflow end-to-end, file outputs, stages

Run all:
    python -m unittest discover -s tests -p "test_article_workflow*.py"

Or run this file directly to load all sub-modules:
    python test_article_workflow.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_article_workflow_normalize import TestNormalizeWorkflowRequest
from test_article_workflow_draft import (
    TestBuildBriefPayload,
    TestBuildDraftPayload,
    TestBuildRevisionTemplate,
)
from test_article_workflow_summary import (
    TestCleanTextListPreview,
    TestSummarizeAssetStage,
    TestSummarizeBriefDecisions,
    TestSummarizeDraftDecisions,
    TestSummarizeFeedbackStage,
    TestSummarizeLearningRulesPreview,
    TestSummarizeStyleLearningSurface,
)
from test_article_workflow_revision import (
    TestBuildRedTeamReview,
    TestDerivePersistFeedback,
    TestHasBoundaryLanguage,
    TestReorderCandidates,
    TestRequestNeedsPackageRebuild,
    TestRewriteRequestAfterAttack,
)
from test_article_workflow_integration import (
    TestBuildDecisionTrace,
    TestBuildReportMarkdown,
    TestRunArticleWorkflowIntegration,
)


if __name__ == "__main__":
    unittest.main()
