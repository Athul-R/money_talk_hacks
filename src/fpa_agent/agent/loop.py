"""LangChain writer ↔ validator agent loop.

The run only succeeds when the validation agent passes.
Writer drafts → Validator audits → (rewrite) → repeat until pass or max rounds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from fpa_agent.agent.langchain_llm import get_chat_model
from fpa_agent.agent.prompts import EXEC_REWRITE_SYSTEM_LC, EXEC_WRITER_SYSTEM_LC
from fpa_agent.agent.validator import ValidationIssue, ValidationResult, deterministic_validate

WRITER_SYSTEM = EXEC_WRITER_SYSTEM_LC
REWRITE_SYSTEM = EXEC_REWRITE_SYSTEM_LC

VALIDATOR_SYSTEM = """You are an FP&A evidence auditor (validation agent).
Validate the SUMMARY strictly against EVIDENCE JSON.
The summary should read as a one-page executive revenue brief, but grounding rules still apply.
Fail if: evaluative adjectives without number+baseline; numbers absent from evidence;
invented causality (deals, AI demand, targeting, management intent);
KPI treated as $ partition of revenue.
Do NOT fail merely because the tone is narrative or executive rather than tabular.
Return ONLY JSON with keys: passed (bool), notes (string), issues (array of
{{severity, code, message, excerpt}}).
passed must be true ONLY if the summary is fully grounded."""


@dataclass
class AgentLoopResult:
    summary: str
    passed: bool
    rounds: int
    history: list[dict[str, Any]] = field(default_factory=list)
    validation: ValidationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "passed": self.passed,
            "rounds": self.rounds,
            "history": self.history,
            "validation": self.validation.to_dict() if self.validation else {},
        }


def _content_text(msg: Any) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content).strip()


def _parse_judge_json(raw: str) -> tuple[bool, str, list[ValidationIssue]]:
    extra: list[ValidationIssue] = []
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        data = json.loads(raw[start : end + 1] if start >= 0 and end >= 0 else raw)
        passed = bool(data.get("passed"))
        notes = str(data.get("notes") or "")
        for item in data.get("issues") or []:
            extra.append(
                ValidationIssue(
                    severity=str(item.get("severity") or "error"),
                    code=str(item.get("code") or "llm_judge"),
                    message=str(item.get("message") or ""),
                    excerpt=str(item.get("excerpt") or ""),
                )
            )
        return passed, notes, extra
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            f"validator_json_parse_error: {exc}",
            [
                ValidationIssue(
                    severity="error",
                    code="validator_json_parse_error",
                    message="Validation agent did not return parseable JSON — treat as FAIL.",
                )
            ],
        )


def run_validation_agent(summary: str, evidence: dict[str, Any], llm: Any) -> ValidationResult:
    """Validation agent: deterministic rules + LangChain LLM judge.

    Passes ONLY when there are zero deterministic errors AND the LLM judge returns passed=true.
    """
    det = deterministic_validate(summary, evidence)

    judge_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", VALIDATOR_SYSTEM),
            (
                "human",
                "EVIDENCE:\n{evidence}\n\nSUMMARY:\n{summary}\n\nDETERMINISTIC_ISSUES:\n{det_issues}",
            ),
        ]
    )
    judge_chain = judge_prompt | llm | RunnableLambda(_content_text)
    raw = judge_chain.invoke(
        {
            "evidence": json.dumps(evidence, default=str),
            "summary": summary,
            "det_issues": json.dumps([i.to_dict() for i in det], default=str),
        }
    )
    llm_passed, notes, llm_issues = _parse_judge_json(raw)
    issues = det + llm_issues
    errors = [i for i in issues if i.severity == "error"]

    # Strict gate: both deterministic clean AND validation-agent LLM pass
    passed = (len(errors) == 0) and llm_passed

    return ValidationResult(
        passed=passed,
        issues=issues,
        summary_validated=summary,
        rewritten=False,
        llm_judge_notes=notes,
    )


def run_writer_agent(evidence: dict[str, Any], llm: Any, *, feedback: dict[str, Any] | None = None) -> str:
    """Writer agent: draft or rewrite an executive one-pager from evidence."""
    company = evidence.get("company", "Company")
    period = evidence.get("period", "")
    prior = evidence.get("prior_period", "")
    brief_header = f"Write the one-page brief for {company}: {period} vs {prior}."

    if feedback:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", REWRITE_SYSTEM),
                (
                    "human",
                    "{header}\n\nEVIDENCE:\n{evidence}\n\nORIGINAL_SUMMARY:\n{summary}\n\nISSUES_TO_FIX:\n{issues}",
                ),
            ]
        )
        chain = prompt | llm | RunnableLambda(_content_text)
        return chain.invoke(
            {
                "header": brief_header,
                "evidence": json.dumps(evidence, default=str),
                "summary": feedback.get("summary", ""),
                "issues": json.dumps(feedback.get("issues", []), default=str),
            }
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", WRITER_SYSTEM),
            ("human", "{header}\n\nEVIDENCE JSON:\n{evidence}"),
        ]
    )
    chain = prompt | llm | RunnableLambda(_content_text)
    return chain.invoke(
        {
            "header": brief_header,
            "evidence": json.dumps(evidence, default=str),
        }
    )


def run_agent_loop(
    evidence: dict[str, Any],
    *,
    max_rounds: int = 3,
    temperature: float = 0.0,
) -> AgentLoopResult:
    """LangChain agent loop: write → validate → rewrite until validation passes.

    The loop result.passed is True ONLY if the validation agent succeeds.
    """
    llm = get_chat_model(temperature=temperature, max_tokens=1800)
    history: list[dict[str, Any]] = []
    summary = ""
    validation: ValidationResult | None = None

    for round_i in range(1, max_rounds + 1):
        if round_i == 1:
            summary = run_writer_agent(evidence, llm)
        else:
            assert validation is not None
            summary = run_writer_agent(
                evidence,
                llm,
                feedback={
                    "summary": summary,
                    "issues": [i.to_dict() for i in validation.issues],
                },
            )

        validation = run_validation_agent(summary, evidence, llm)
        history.append(
            {
                "round": round_i,
                "passed": validation.passed,
                "issue_count": len(validation.issues),
                "error_count": sum(1 for i in validation.issues if i.severity == "error"),
                "notes": validation.llm_judge_notes[:500],
            }
        )

        if validation.passed:
            validation.summary_validated = summary
            validation.rewritten = round_i > 1
            return AgentLoopResult(
                summary=summary,
                passed=True,
                rounds=round_i,
                history=history,
                validation=validation,
            )

    # Exhausted rounds without validator success → FAIL
    assert validation is not None
    validation.summary_validated = summary
    validation.rewritten = max_rounds > 1
    validation.passed = False  # enforce: cannot pass without validator success
    return AgentLoopResult(
        summary=summary,
        passed=False,
        rounds=max_rounds,
        history=history,
        validation=validation,
    )
