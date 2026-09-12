from typing import Any
from gpd.sessions.completion import CompletionInput


class KnowledgeExtractionWorkflow:
    VERSION = "1.0"

    def extract(self, input: CompletionInput) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        summary = (input.agent_summary or "").strip()
        
        if summary:
            # Determine type
            item_type = "technical_discovery"
            lower = summary.lower()
            if "decision" in lower or "decided" in lower:
                item_type = "decision"
            elif "rule" in lower or "convention" in lower:
                item_type = "architecture_rule"
            elif "constraint" in lower or "timeout" in lower or "retry" in lower:
                item_type = "implementation_constraint"

            title_words = summary.split()[:8]
            title = " ".join(title_words).rstrip(".")
            if not title:
                title = f"Knowledge from Task {input.task_id}"

            evidence: list[dict[str, Any]] = [
                {
                    "evidence_type": "agent_summary",
                    "target_id": "summary",
                    "detail": summary[:200],
                }
            ]
            if input.task_id:
                evidence.append(
                    {
                        "evidence_type": "task",
                        "target_id": input.task_id,
                        "detail": f"Derived from task {input.task_id}",
                    }
                )
            for cf in input.changed_files[:3]:
                evidence.append(
                    {
                        "evidence_type": "changed_file",
                        "target_id": cf.path,
                        "detail": f"File modified: {cf.path}",
                    }
                )

            proposals.append(
                {
                    "type": item_type,
                    "title": title,
                    "content": summary,
                    "confidence": 0.92,
                    "evidence": evidence,
                }
            )

        return proposals
