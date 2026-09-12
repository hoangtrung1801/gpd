from gpd.context.schemas import ContextRequest


class ContextQueryBuilder:
    def build_query(self, request: ContextRequest) -> str:
        parts: list[str] = []
        if request.developer_prompt:
            parts.append(request.developer_prompt.strip())
        if request.task_title:
            parts.append(request.task_title.strip())
        if request.task_description:
            parts.append(request.task_description.strip())
        return " ".join(parts)
