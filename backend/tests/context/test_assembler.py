from pathlib import Path
import pytest
from gpd.context.assembler import ContextAssembler, ContextRequest
from gpd.context.schemas import CandidateEntry, ContextPackage


def test_context_keeps_task_facts_and_high_conflicts_under_budget(database):
    assembler = ContextAssembler(database)
    # Simulate high severity conflict on session
    package = assembler.assemble(
        ContextRequest(
            project_id="p1",
            session_id="s1",
            task_id="BUG-1",
            developer_prompt="fix the loading state",
            token_budget=900,
            task_title="Checkout hangs on expired card",
            actual_behavior="API returns 400 and UI hangs",
            expected_behavior="Show error banner and allow retry",
            high_conflicts=["Avoid editing src/payment/service.ts until session s2 completes"],
        )
    )
    sections = [entry.section for entry in package.entries]
    assert sections[:2] == ["task", "expected_actual"]
    assert "work_warnings" in sections or "high_severity_conflicts" in sections
    assert package.estimated_tokens <= 900


def test_mandatory_overflow_compacts_but_keeps_title_and_warnings(database):
    assembler = ContextAssembler(database)
    package = assembler.assemble(
        ContextRequest(
            project_id="p1",
            session_id="s1",
            task_id="BUG-1",
            developer_prompt="fix loading",
            token_budget=50,
            task_title="Checkout hangs on expired card",
            actual_behavior="UI hangs indefinitely after expired card error",
            expected_behavior="Show card error message and reset submit button",
            high_conflicts=["Avoid editing src/payment/service.ts"],
        )
    )
    assert "budget_exceeded_by_mandatory" in package.warnings
    assert package.estimated_tokens <= 50
    # Mandatory facts still preserved in package
    content_blob = " ".join(entry.content for entry in package.entries)
    assert "Checkout hangs" in content_blob or "Checkout" in content_blob
    assert "UI hangs" in content_blob or "Show card error" in content_blob


def test_both_indexes_down_produces_minimal_package_with_warnings(database):
    assembler = ContextAssembler(database)
    package = assembler.assemble(
        ContextRequest(
            project_id="p1",
            session_id="s1",
            task_id="BUG-1",
            token_budget=500,
            task_title="Bug Title",
            actual_behavior="Bug Actual",
            expected_behavior="Bug Expected",
            lexical_available=False,
            vector_available=False,
        )
    )
    assert "lexical_search_unavailable" in package.warnings
    assert "vector_search_unavailable" in package.warnings
    # Mandatory sections still present
    sections = [entry.section for entry in package.entries]
    assert "task" in sections
    assert "expected_actual" in sections
