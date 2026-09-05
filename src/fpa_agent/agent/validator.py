"""Validation agent: check FP&A prose against evidence (no ungrounded adjectives / invented facts)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from fpa_agent.agent.llm import complete, llm_available

# Soft language that requires an immediate numeric + baseline grounding.
BANNED_ADJECTIVES = [
    "strong",
    "stronger",
    "strongly",
    "weak",
    "weaker",
    "good",
    "bad",
    "major",
    "minor",
    "exceptional",
    "notable",
    "notably",
    "significant",
    "significantly",
    "solid",
    "robust",
    "impressive",
    "standout",
    "healthy",
    "soft",
    "acceleration",
    "momentum",
    "outperformance",
    "underperformance",
    "remarkable",
    "dramatic",
    "massive",
    "modest",  # still evaluative unless quantified
]

BANNED_PHRASES = [
    "growth engine",
    "step-up",
    "step up",
    "large deal",
    "multi-year commitment",
    "ai demand",
    "ai/infrastructure demand",
    "improved ad relevance",
    "better targeting",
    "pricing power",
    "signaling a shift",
    "suggests that",
    "this suggests",
    "implied by",
]

# Speculative / causal invention patterns (not in arithmetic evidence)
INVENTION_PATTERNS = [
    r"\bdeal wins?\b",
    r"\bmulti[- ]year\b",
    r"\bcustomer acquisition\b",
    r"\btargeting\b",
    r"\bad relevance\b",
    r"\bAI(?:/|\s+)?infrastructure demand\b",
    r"\bmanagement (?:said|attributes|believes)\b",
]


@dataclass
class ValidationIssue:
    severity: str  # error | warning
    code: str
    message: str
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    summary_validated: str = ""
    rewritten: bool = False
    llm_judge_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "summary_validated": self.summary_validated,
            "rewritten": self.rewritten,
            "llm_judge_notes": self.llm_judge_notes,
        }


def _window_around(text: str, start: int, end: int, pad: int = 48) -> str:
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    return text[a:b].replace("\n", " ")


def _has_nearby_number(text: str, start: int, end: int, radius: int = 80) -> bool:
    window = text[max(0, start - radius) : min(len(text), end + radius)]
    return bool(
        re.search(
            r"(\$?\d[\d,]*(?:\.\d+)?\s*%|\bz\s*=?\s*-?\d+(?:\.\d+)?|Δ\s*=?\s*-?\$?\d|\+\s*\$?\d|−\s*\$?\d|-\s*\$?\d)",
            window,
            flags=re.IGNORECASE,
        )
    )


def _has_nearby_baseline(text: str, start: int, end: int, prior_period: str, radius: int = 100) -> bool:
    window = text[max(0, start - radius) : min(len(text), end + radius)].lower()
    needles = [
        "vs ",
        "versus",
        "yoy",
        "qoq",
        "trailing history",
        "prior",
        "baseline",
        "share of",
        "of parent",
        "of total",
    ]
    if prior_period:
        needles.append(prior_period.lower())
    return any(n in window for n in needles)


def collect_evidence_numbers(evidence: dict[str, Any]) -> set[float]:
    """Flatten numeric evidence into a tolerance-checkable set."""
    nums: set[float] = set()

    def add(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            nums.add(float(x))
            # also common display scales
            nums.add(round(float(x), 1))
            nums.add(round(float(x), 2))
            if abs(float(x)) >= 1000:
                nums.add(round(float(x) / 1000.0, 1))  # sometimes shown as billions from millions
                nums.add(round(float(x) / 1000.0, 2))

    add(evidence.get("revenue_delta"))
    add(evidence.get("revenue_pct"))
    add(evidence.get("revenue_z"))
    add(evidence.get("revenue_value"))
    add(evidence.get("revenue_prior_value"))
    if evidence.get("revenue_pct") is not None:
        add(float(evidence["revenue_pct"]) * 100.0)

    for key in ("dollar_attribution_clusters", "operational_kpi_clusters", "clusters"):
        for c in evidence.get(key) or []:
            add(c.get("total_delta"))
            add(c.get("mean_z"))
            for d in c.get("drivers") or []:
                add(d.get("delta"))
                add(d.get("pct_change"))
                add(d.get("z_score"))
                add(d.get("share_of_parent_delta"))
                if d.get("pct_change") is not None:
                    add(float(d["pct_change"]) * 100.0)
                if d.get("share_of_parent_delta") is not None:
                    add(float(d["share_of_parent_delta"]) * 100.0)

    for s in evidence.get("companion_metrics") or []:
        add(s.get("delta"))
        add(s.get("pct_change"))
        add(s.get("z_score"))
        add(s.get("value"))
        add(s.get("prior_value"))
        if s.get("pct_change") is not None:
            add(float(s["pct_change"]) * 100.0)

    return nums


def _number_in_evidence(value: float, evidence_nums: set[float], rel_tol: float = 0.03, abs_tol: float = 0.05) -> bool:
    for e in evidence_nums:
        if abs(e - value) <= abs_tol:
            return True
        if e != 0 and abs(e - value) / abs(e) <= rel_tol:
            return True
        # billion display of million evidence
        if abs(e) >= 100 and abs(e / 1000.0 - value) <= abs_tol:
            return True
        if abs(e) >= 100 and e != 0 and abs(e / 1000.0 - value) / abs(e / 1000.0) <= rel_tol:
            return True
    return False


def deterministic_validate(summary: str, evidence: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    prior = str(evidence.get("prior_period") or "")
    text = summary or ""

    # 1) Banned adjectives without nearby number + baseline
    for word in BANNED_ADJECTIVES:
        for m in re.finditer(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE):
            if not _has_nearby_number(text, m.start(), m.end()) or not _has_nearby_baseline(
                text, m.start(), m.end(), prior
            ):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="ungrounded_adjective",
                        message=(
                            f"Adjective '{word}' lacks a nearby number and explicit baseline "
                            f"(vs {prior or 'prior_period'} / trailing history)."
                        ),
                        excerpt=_window_around(text, m.start(), m.end()),
                    )
                )

    # 2) Banned phrases
    lower = text.lower()
    for phrase in BANNED_PHRASES:
        idx = lower.find(phrase)
        if idx >= 0:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="banned_phrase",
                    message=f"Banned ungrounded phrase: '{phrase}'.",
                    excerpt=_window_around(text, idx, idx + len(phrase)),
                )
            )

    # 3) Invention / speculative causality
    for pat in INVENTION_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invented_causality",
                    message=f"Possible invented causal claim matching /{pat}/ — not supported by arithmetic evidence.",
                    excerpt=_window_around(text, m.start(), m.end()),
                )
            )

    # 4) Numbers in prose should match evidence (tolerance)
    evidence_nums = collect_evidence_numbers(evidence)
    # capture percents, dollars, plain floats, z-scores
    num_patterns = [
        (r"z(?:-score)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*σ?", "z"),
        (r"([+-]?\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?)\s*[Bb]?", "money"),
        (r"([+-]?\$?\d+(?:\.\d+)?)\s*[Bb](?!\w)", "billions"),
        (r"([+-]?\d+(?:\.\d+)?)\s*%", "pct"),
    ]
    seen: set[tuple[str, float]] = set()
    for pat, kind in num_patterns:
        for m in re.finditer(pat, text):
            raw = m.group(1)
            cleaned = raw.replace("$", "").replace(",", "").replace("+", "")
            try:
                val = float(cleaned)
            except ValueError:
                continue
            if kind == "billions":
                # compare both as billions and as millions*1000
                candidates = [val, val * 1000.0]
            elif kind == "pct":
                candidates = [val, val / 100.0]
            else:
                candidates = [val]
            key = (kind, round(val, 4))
            if key in seen:
                continue
            seen.add(key)
            if any(_number_in_evidence(c, evidence_nums) for c in candidates):
                continue
            # allow tiny integers used as list indices / section numbers
            if kind == "money" and val.is_integer() and abs(val) <= 10:
                continue
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="number_not_in_evidence",
                    message=f"Number '{raw}' ({kind}) not found in evidence within tolerance.",
                    excerpt=_window_around(text, m.start(), m.end()),
                )
            )

    # 5) Require baseline mention somewhere when deltas are discussed
    if re.search(r"(\+|−|-)?\$?\d", text) and prior:
        if prior not in text and "trailing history" not in text.lower() and " vs " not in text.lower():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_baseline",
                    message=f"Summary cites numbers but never names baseline '{prior}' or 'trailing history'.",
                )
            )

    return issues


def llm_judge(summary: str, evidence: dict[str, Any], deterministic_issues: list[ValidationIssue]) -> tuple[bool, str, list[ValidationIssue]]:
    """Ask Claude to judge grounding; returns (passed, notes, extra_issues)."""
    if not llm_available():
        return (len([i for i in deterministic_issues if i.severity == "error"]) == 0, "llm_judge_skipped", [])

    system = (
        "You are an FP&A evidence auditor.\n"
        "Validate the SUMMARY strictly against EVIDENCE JSON.\n"
        "Fail if: evaluative adjectives without number+baseline; numbers absent from evidence; "
        "invented causality (deals, AI demand, targeting, management intent); "
        "KPI treated as $ partition of revenue.\n"
        "Return ONLY JSON with keys: passed (bool), notes (string), issues (array of "
        "{severity, code, message, excerpt})."
    )
    user = json.dumps(
        {
            "evidence": evidence,
            "summary": summary,
            "deterministic_issues": [i.to_dict() for i in deterministic_issues],
        },
        default=str,
    )
    raw = complete(system, user, temperature=0.0, max_tokens=1500)
    extra: list[ValidationIssue] = []
    notes = raw
    passed = False
    try:
        # extract JSON object if model wraps it
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
    except Exception as exc:  # noqa: BLE001
        notes = f"llm_judge_parse_error: {exc}; raw={raw[:500]}"
        passed = False
        extra.append(
            ValidationIssue(
                severity="warning",
                code="llm_judge_parse_error",
                message="Validator LLM did not return parseable JSON.",
            )
        )
    return passed, notes, extra


def rewrite_summary(summary: str, evidence: dict[str, Any], issues: list[ValidationIssue]) -> str:
    """Ask writer model to produce a corrected summary that fixes validation issues."""
    system = (
        "Rewrite the FP&A summary so it passes audit.\n"
        "Keep only claims grounded in EVIDENCE.\n"
        "Every material claim must include delta and/or % vs prior_period and/or z vs trailing history "
        "and/or share of parent delta.\n"
        "Do not use evaluative adjectives. Do not invent causality.\n"
        "Return only the rewritten summary markdown."
    )
    user = json.dumps(
        {
            "prior_period": evidence.get("prior_period"),
            "period": evidence.get("period"),
            "evidence": evidence,
            "original_summary": summary,
            "issues_to_fix": [i.to_dict() for i in issues],
        },
        default=str,
    )
    return complete(system, user, temperature=0.0, max_tokens=1800)


def validate_summary(
    summary: str,
    evidence: dict[str, Any],
    *,
    rewrite_on_fail: bool = True,
    max_rounds: int = 1,
) -> ValidationResult:
    """Run deterministic checks + LLM judge; optionally rewrite once on failure."""
    current = summary
    rewritten = False
    all_notes: list[str] = []

    for round_i in range(max_rounds + 1):
        det = deterministic_validate(current, evidence)
        llm_passed, notes, llm_issues = llm_judge(current, evidence, det)
        all_notes.append(notes)
        issues = det + llm_issues
        errors = [i for i in issues if i.severity == "error"]
        # Prefer deterministic errors; LLM pass alone cannot clear deterministic errors
        passed = (len(errors) == 0) and (llm_passed or not llm_available())

        if passed:
            return ValidationResult(
                passed=True,
                issues=issues,
                summary_validated=current,
                rewritten=rewritten,
                llm_judge_notes=" | ".join(all_notes),
            )

        if rewrite_on_fail and round_i < max_rounds and llm_available():
            current = rewrite_summary(current, evidence, issues)
            rewritten = True
            continue

        return ValidationResult(
            passed=False,
            issues=issues,
            summary_validated=current,
            rewritten=rewritten,
            llm_judge_notes=" | ".join(all_notes),
        )

    return ValidationResult(passed=False, issues=[], summary_validated=current, rewritten=rewritten)
