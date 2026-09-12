import pytest

from gpd.llm.workflows.bug_extraction import (
    BugExtraction,
    BugExtractionWorkflow,
    InvalidEvidenceReference,
)

pytestmark = pytest.mark.asyncio


def valid_bug_payload(title_evidence=None, env_value=None):
    if title_evidence is None:
        title_evidence = ["m1"]
    return {
        "title": {"value": "Checkout hangs on expired card", "confidence": 0.98, "evidence": title_evidence},
        "summary": {"value": "Checkout hang on expired card error handling failure", "confidence": 0.92, "evidence": ["m1"]},
        "description": {"value": "Loading never ends after API returns error.", "confidence": 0.95, "evidence": ["m1", "m3"]},
        "actual_behavior": {"value": "API returns payment_method_invalid and UI keeps loading.", "confidence": 0.99, "evidence": ["m2", "m3"]},
        "expected_behavior": {"value": "Show an error and allow another method.", "confidence": 0.94, "evidence": ["m4"]},
        "environment": {"value": env_value, "confidence": 0.9 if env_value else 0.0, "evidence": []},
        "severity": {"value": "high", "confidence": 0.85, "evidence": []},
        "affected_component": {"value": "payments", "confidence": 0.9, "evidence": []},
        "technical_clues": {"value": ["src/payment/checkout.ts"], "confidence": 0.88, "evidence": []},
        "participants": ["alice", "bob", "carol"],
    }


async def test_bug_extraction_keeps_unknown_environment_empty(fake_llm, bug_workflow, thread):
    fake_llm.respond(
        {
            "title": {"value": "Checkout hangs on expired card", "confidence": 0.98, "evidence": ["m1"]},
            "description": {"value": "Loading never ends after the API error.", "confidence": 0.95, "evidence": ["m1", "m3"]},
            "actual_behavior": {"value": "API returns payment_method_invalid and UI keeps loading.", "confidence": 0.99, "evidence": ["m2", "m3"]},
            "expected_behavior": {"value": "Show an error and allow another method.", "confidence": 0.94, "evidence": ["m4"]},
            "environment": {"value": None, "confidence": 0.0, "evidence": []},
        }
    )
    extraction = await bug_workflow.extract(thread)
    assert extraction.environment.value is None


async def test_bug_extraction_rejects_evidence_outside_thread(fake_llm, bug_workflow, thread):
    # Both initial response and retry response have invalid evidence outside thread
    fake_llm.respond(valid_bug_payload(title_evidence=["not-in-thread"]))
    fake_llm.respond(valid_bug_payload(title_evidence=["still-not-in-thread"]))

    with pytest.raises(InvalidEvidenceReference):
        await bug_workflow.extract(thread)


async def test_bug_extraction_corrective_retry_succeeds(fake_llm, bug_workflow, thread):
    # First response fails evidence validation
    fake_llm.respond(valid_bug_payload(title_evidence=["bad-id"]))
    # Corrective retry returns valid evidence
    fake_llm.respond(valid_bug_payload(title_evidence=["m1"]))

    extraction = await bug_workflow.extract(thread)
    assert extraction.title.value == "Checkout hangs on expired card"
    assert extraction.title.evidence[0].message_id == "m1"
    # Ensure 2 requests were sent to LLM (initial + 1 retry)
    assert len(fake_llm.requests) == 2


async def test_bug_extraction_retains_summary_and_participants(fake_llm, bug_workflow, thread):
    fake_llm.respond(valid_bug_payload())
    extraction = await bug_workflow.extract(thread)

    assert extraction.summary.value == "Checkout hang on expired card error handling failure"
    assert "alice" in extraction.participants
    assert "bob" in extraction.participants
