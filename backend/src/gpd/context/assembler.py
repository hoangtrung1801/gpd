from datetime import datetime, timezone
import re
from typing import Any
import uuid

from gpd.context.budget import TokenBudget, estimate_tokens
from gpd.context.query_builder import ContextQueryBuilder
from gpd.context.repository import ContextRepository
from gpd.context.schemas import (
    CandidateEntry,
    ContextEntry,
    ContextPackage,
    ContextRequest,
)
from gpd.db.engine import Database
from gpd.knowledge.service import KnowledgeService


def new_uuid() -> str:
    return str(uuid.uuid4())


class ContextAssembler:
    def __init__(
        self,
        database: Database,
        repository: ContextRepository | None = None,
        budget: TokenBudget | None = None,
        query_builder: ContextQueryBuilder | None = None,
    ):
        self.database = database
        self.repository = repository or ContextRepository()
        self.budget = budget or TokenBudget()
        self.query_builder = query_builder or ContextQueryBuilder()

    def assemble(self, request: ContextRequest) -> ContextPackage:
        mandatory: list[CandidateEntry] = []
        optional: list[CandidateEntry] = []
        warnings: list[str] = []

        # 1. Search health warnings
        search_health = {
            "lexical": request.lexical_available,
            "vector": request.vector_available,
        }
        if not request.lexical_available:
            warnings.append("lexical_search_unavailable")
        if not request.vector_available:
            warnings.append("vector_search_unavailable")

        # 2. Mandatory: task facts
        task_parts: list[str] = []
        if request.task_title:
            task_parts.append(f"Title: {request.task_title}")
        if request.task_id:
            task_parts.append(f"Task ID: {request.task_id}")
        if request.task_description:
            task_parts.append(f"Description: {request.task_description}")
        task_text = "\n".join(task_parts) if task_parts else "Task details pending."
        mandatory.append(
            CandidateEntry(
                section="task",
                content=task_text,
                token_estimate=estimate_tokens(task_text),
                is_mandatory=True,
                selection_reason="Mandatory task facts",
            )
        )

        # 3. Mandatory: expected / actual behavior
        ea_parts: list[str] = []
        if request.actual_behavior:
            ea_parts.append(f"Actual Behavior:\n{request.actual_behavior}")
        if request.expected_behavior:
            ea_parts.append(f"Expected Behavior:\n{request.expected_behavior}")
        if ea_parts:
            ea_text = "\n\n".join(ea_parts)
            mandatory.append(
                CandidateEntry(
                    section="expected_actual",
                    content=ea_text,
                    token_estimate=estimate_tokens(ea_text),
                    is_mandatory=True,
                    selection_reason="Mandatory bug behavior facts",
                )
            )

        # 4. Conditional mandatory: high severity conflicts
        if request.high_conflicts:
            conflict_text = "\n".join(f"- {c}" for c in request.high_conflicts)
            mandatory.append(
                CandidateEntry(
                    section="work_warnings",
                    content=f"High-Severity Work Overlap Warnings:\n{conflict_text}",
                    token_estimate=estimate_tokens(conflict_text),
                    is_mandatory=True,
                    selection_reason="Conditional mandatory active-work warning",
                )
            )

        # 5. Query confirmed knowledge items for project
        try:
            k_svc = KnowledgeService(self.database)
            confirmed_items = k_svc.list_items(request.project_id, status="confirmed")
            query_text = (self.query_builder.build_query(request) or "").lower()
            query_tokens = set(re.findall(r"\w{3,}", query_text))

            for k_item in confirmed_items:
                item_text = f"{k_item.title} {k_item.content}".lower()
                item_tokens = set(re.findall(r"\w{3,}", item_text))
                overlap_count = len(query_tokens.intersection(item_tokens))
                score = 0.70 + min(0.25, overlap_count * 0.05)
                
                entry_content = f"[{k_item.type.upper()}] {k_item.title}: {k_item.content}"
                optional.append(
                    CandidateEntry(
                        section="requirements_decisions",
                        content=entry_content,
                        knowledge_id=k_item.id,
                        score=score,
                        score_components={"base": 0.70, "overlap": min(0.25, overlap_count * 0.05)},
                        selection_reason=f"Confirmed {k_item.type} matching project context",
                        token_estimate=estimate_tokens(entry_content),
                    )
                )
        except Exception:
            pass

        # 6. Token budget selection
        selected_candidates, budget_warnings = self.budget.select(
            mandatory=mandatory,
            optional=optional,
            limit=request.token_budget,
        )
        warnings.extend(budget_warnings)

        # 7. Build immutable package entries
        entries: list[ContextEntry] = []
        for rank, c in enumerate(selected_candidates, start=1):
            entries.append(
                ContextEntry(
                    id=new_uuid(),
                    section=c.section,
                    content=c.content,
                    source_id=c.source_id,
                    knowledge_id=c.knowledge_id,
                    score=c.score,
                    score_components=c.score_components,
                    selection_reason=c.selection_reason,
                    rank=rank,
                    token_estimate=c.token_estimate,
                )
            )

        total_tokens = sum(e.token_estimate for e in entries)
        pkg_id = new_uuid()
        dev_query = self.query_builder.build_query(request) or None

        package = ContextPackage(
            id=pkg_id,
            session_id=request.session_id,
            task_id=request.task_id,
            developer_query=dev_query,
            token_budget=request.token_budget,
            estimated_tokens=total_tokens,
            renderer_version="1.0",
            search_health_snapshot=search_health,
            warnings=warnings,
            entries=entries,
        )

        # 8. Persist to database
        def _txn():
            with self.database.session() as session:
                with session.begin():
                    self.repository.save_package(session, package)

        try:
            _txn()
        except Exception:
            pass

        return package
