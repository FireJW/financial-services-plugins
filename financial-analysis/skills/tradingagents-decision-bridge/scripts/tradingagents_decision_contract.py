from __future__ import annotations

from typing import Any


LAYER_VALUE = "decision_advisory"
SOURCE_VALUE = "tradingagents-decision-bridge"
STATUS_VALUES = {"ready", "partial", "skipped", "error"}
ACTION_VALUES = {"buy", "sell", "hold", "no_opinion"}
CONFIDENCE_VALUES = {"low", "medium", "high"}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def contract_errors(memo: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if clean_text(memo.get("layer")) != LAYER_VALUE:
        errors.append("layer must equal decision_advisory")
    if clean_text(memo.get("source")) != SOURCE_VALUE:
        errors.append("source must equal tradingagents-decision-bridge")
    if clean_text(memo.get("version")) == "":
        errors.append("version is required")
    if clean_text(memo.get("requested_ticker")) == "":
        errors.append("requested_ticker is required")
    if clean_text(memo.get("normalized_ticker")) == "":
        errors.append("normalized_ticker is required")
    if clean_text(memo.get("upstream_ticker")) == "":
        errors.append("upstream_ticker is required")
    if clean_text(memo.get("analysis_date")) == "":
        errors.append("analysis_date is required")

    status = clean_text(memo.get("status"))
    if status not in STATUS_VALUES:
        errors.append("status must be one of ready, partial, skipped, error")

    input_summary = safe_dict(memo.get("input_summary"))
    if not isinstance(input_summary.get("evidence_count"), int):
        errors.append("input_summary.evidence_count must be an int")
    if not isinstance(input_summary.get("catalyst_count"), int):
        errors.append("input_summary.catalyst_count must be an int")
    if not isinstance(input_summary.get("market_context_available"), bool):
        errors.append("input_summary.market_context_available must be a bool")

    for case_name in ("bull_case", "bear_case"):
        case = safe_dict(memo.get(case_name))
        if not isinstance(case.get("key_arguments"), list):
            errors.append(f"{case_name}.key_arguments must be a list")
        confidence = clean_text(case.get("confidence"))
        if confidence and confidence not in CONFIDENCE_VALUES:
            errors.append(f"{case_name}.confidence must be low, medium, or high")
        if not isinstance(case.get("supporting_evidence_refs"), list):
            errors.append(f"{case_name}.supporting_evidence_refs must be a list")

    risk = safe_dict(memo.get("risk_assessment"))
    if not isinstance(risk.get("key_risks"), list):
        errors.append("risk_assessment.key_risks must be a list")
    if not isinstance(risk.get("liquidity_concern"), bool):
        errors.append("risk_assessment.liquidity_concern must be a bool")

    decision = safe_dict(memo.get("decision"))
    action = clean_text(decision.get("action"))
    conviction = clean_text(decision.get("conviction"))
    if action not in ACTION_VALUES:
        errors.append("decision.action must be buy, sell, hold, or no_opinion")
    if conviction and conviction not in CONFIDENCE_VALUES:
        errors.append("decision.conviction must be low, medium, or high")
    if clean_text(decision.get("rationale")) == "":
        errors.append("decision.rationale is required")

    cost_summary = safe_dict(memo.get("cost_summary"))
    if not isinstance(cost_summary.get("requested_budget_tokens"), int):
        errors.append("cost_summary.requested_budget_tokens must be an int")
    if not isinstance(cost_summary.get("timeout_seconds"), int):
        errors.append("cost_summary.timeout_seconds must be an int")

    for list_name in ("key_disagreements", "invalidation_triggers", "pair_basket_ideas", "warnings"):
        if not isinstance(memo.get(list_name), list):
            errors.append(f"{list_name} must be a list")

    warnings = safe_list(memo.get("warnings"))
    if not warnings:
        errors.append("warnings must contain at least one item")

    return errors


def validate_decision_memo(memo: dict[str, Any]) -> bool:
    return not contract_errors(memo)
