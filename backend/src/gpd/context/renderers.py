from typing import Any
from gpd.context.schemas import ContextPackage

SECTION_TITLES = {
    "task": "TASK",
    "expected_actual": "EXPECTED / ACTUAL BEHAVIOR",
    "discussion": "ORIGINAL DISCUSSION",
    "requirements_decisions": "CONFIRMED REQUIREMENTS & DECISIONS",
    "files": "RELATED FILES",
    "work_warnings": "ACTIVE-WORK WARNINGS",
    "high_severity_conflicts": "ACTIVE-WORK WARNINGS",
    "contradictions": "CONTRADICTORY CONTEXT",
    "background": "BACKGROUND",
}


class TextContextRenderer:
    def render(self, package: ContextPackage) -> str:
        lines: list[str] = []
        
        # Banners for warnings
        for w in package.warnings:
            lines.append(f"=== WARNING: {w} ===")
        if package.warnings:
            lines.append("")

        current_section = None
        for entry in package.entries:
            title = SECTION_TITLES.get(entry.section, entry.section.upper().replace("_", " "))
            if title != current_section:
                current_section = title
                lines.append(f"## {title}")
                lines.append("")
            lines.append(entry.content)
            lines.append("")

        return "\n".join(lines).strip()


class JsonContextRenderer:
    def render(self, package: ContextPackage) -> dict[str, Any]:
        return {
            "id": package.id,
            "session_id": package.session_id,
            "task_id": package.task_id,
            "developer_query": package.developer_query,
            "token_budget": package.token_budget,
            "estimated_tokens": package.estimated_tokens,
            "renderer_version": package.renderer_version,
            "search_health_snapshot": package.search_health_snapshot,
            "warnings": package.warnings,
            "entries": [entry.model_dump(mode="json") for entry in package.entries],
            "created_at": package.created_at,
        }
