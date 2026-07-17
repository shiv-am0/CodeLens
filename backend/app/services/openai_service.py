import json
from typing import List, Optional
from openai import AsyncOpenAI
from loguru import logger

from app.core.config import settings
from app.services.key_manager import key_manager


class OpenAIService:
    def __init__(self):
        self.provider = settings.llm_provider
        self.model = settings.openai_chat_model
        self.embedding_model = settings.openai_embedding_model
        self.embedding_dim = settings.openai_embedding_dim

        if self.provider == "ollama":
            self._ollama_client = AsyncOpenAI(
                base_url=settings.ollama_base_url,
                api_key="ollama",
            )
            self.model = settings.ollama_chat_model
            self.embedding_model = settings.ollama_embedding_model
            self.embedding_dim = settings.ollama_embedding_dim
        else:
            self._ollama_client = None

    async def _get_client(self) -> AsyncOpenAI | None:
        if self.provider == "ollama":
            return self._ollama_client
        return await key_manager.get_client()

    async def generate_completion(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        client = await self._get_client()
        if not client:
            return f"{self.provider} not configured. Please set the appropriate API key or provider."

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""

    async def generate_structured(self, system_prompt: str, user_prompt: str, response_format: dict) -> dict:
        client = await self._get_client()
        if not client:
            return {"error": f"{self.provider} not configured. Please set the appropriate API key or provider."}

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.3,
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}

    async def generate_embedding(self, text: str) -> List[float]:
        client = await self._get_client()
        if not client:
            return [0.0] * self.embedding_dim

        response = await client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        client = await self._get_client()
        if not client:
            return [[0.0] * self.embedding_dim for _ in texts]

        response = await client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    async def chat_with_context(self, question: str, context: str, repo_name: str, chat_history: List[dict] = None) -> str:
        client = await self._get_client()
        if not client:
            return f"{self.provider} not configured. Please set the appropriate API key or provider."

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a Senior Staff Engineer who has worked on this project for years. "
                    "You are helping a new team member understand the codebase. "
                    "Be precise, cite specific files and code patterns when answering. "
                    "Never hallucinate. If you don't know something, say so. "
                    f"The repository is: {repo_name}\n\n"
                    "Context from the codebase:\n" + context[:80000]
                ),
            }
        ]

        if chat_history:
            for entry in chat_history[-10:]:
                messages.append({"role": "user", "content": entry["question"]})
                messages.append({"role": "assistant", "content": entry["answer"]})

        messages.append({"role": "user", "content": question})

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
