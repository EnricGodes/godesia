"""Regression tests for the QueryRouter, driven by data/test_bank.json."""

import json
import re
from pathlib import Path

import pytest

BANK_PATH = Path(__file__).parent.parent.parent / "data" / "test_bank.json"


def _normalize(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def _load_approved_cases():
    """Load only approved cases from the test bank."""
    if not BANK_PATH.exists():
        return []
    with open(BANK_PATH) as f:
        bank = json.load(f)
    return [c for c in bank.get("cases", []) if c.get("verdict") == "approved"]


_cases = _load_approved_cases()


@pytest.mark.skipif(not _cases, reason="No approved test cases in test_bank.json")
@pytest.mark.parametrize(
    "case",
    _cases,
    ids=lambda c: c["question"][:70],
)
def test_approved_answer(router, case):
    """Verify that approved answers haven't changed."""
    result = router.route(case["question"])
    assert result is not None, f"Router returned None for: {case['question']}"

    snapshot = case.get("approved_snapshot", {})
    expected_answer = _normalize(snapshot.get("answer", ""))
    actual_answer = _normalize(result.get("answer", ""))

    assert actual_answer == expected_answer, (
        f"REGRESSION: Answer changed for '{case['question']}'\n"
        f"  Expected: {expected_answer[:200]}\n"
        f"  Got:      {actual_answer[:200]}"
    )
