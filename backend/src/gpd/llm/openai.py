import json
import os
from pathlib import Path
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel
from gpd.llm.gateway import LlmGateway, LlmStructuredRequest, LlmStructuredResponse

T = TypeVar("T", bound=BaseModel)

class OpenAILlmGateway(LlmGateway):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            for env_path in [Path(".env"), Path("/home/work/gpd/.env")]:
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        if line.startswith("OPENAI_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip("\"'")
                            break
                if key:
                    break
        self.api_key = key

        raw_model = model or os.getenv("GPD_LLM_MODEL") or "gpt-4o"
        if "gpt-5" in raw_model.lower() or "luna" in raw_model.lower():
            self.model = "gpt-4o"
        else:
            self.model = raw_model
    async def generate_structured(
        self, request: LlmStructuredRequest, output_type: type[T]
    ) -> tuple[T, LlmStructuredResponse]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        schema = output_type.model_json_schema()
        system_prompt = (
            "You are an expert AI assistant that extracts structured bug details from conversations. "
            "You must output valid JSON conforming to the requested schema."
        )
        user_prompt = f"{request.prompt}\n\nPlease output JSON conforming to the schema:\n{json.dumps(schema)}"

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            res_data = resp.json()

        content = res_data["choices"][0]["message"]["content"]
        parsed_dict = json.loads(content)
        parsed_obj = output_type.model_validate(parsed_dict)

        usage = res_data.get("usage", {})
        meta = LlmStructuredResponse(
            data=parsed_dict,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=res_data.get("model", self.model),
            provider="openai",
        )
        return parsed_obj, meta

    async def generate_text(self, prompt: str, system: str | None = None) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        system_prompt = system or "You are GPD, a helpful AI assistant for developers in Slack."
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            res_data = resp.json()

        return res_data["choices"][0]["message"]["content"]
