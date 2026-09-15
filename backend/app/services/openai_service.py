import json
from typing import List

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.ai_configuration import (
    AIConfigurationRequiredError,
    RuntimeAIConfiguration,
    runtime_ai_configuration,
)
from app.services.key_manager import key_manager


class OpenAIService:
    async def _get_client_and_configuration(
        self,
    ) -> tuple[AsyncOpenAI, RuntimeAIConfiguration]:
        configuration = await runtime_ai_configuration.get()
        if configuration.provider == "ollama":
            return (
                AsyncOpenAI(base_url=settings.ollama_base_url, api_key="ollama"),
                RuntimeAIConfiguration(
                    provider="ollama",
                    chat_model=settings.ollama_chat_model,
                    embedding_model=settings.ollama_embedding_model,
                ),
            )

        client = await key_manager.get_client()
        if client is None:
            raise AIConfigurationRequiredError(["api_key"])
        return client, configuration

    async def generate_completion(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 4096
    ) -> str:
        client, configuration = await self._get_client_and_configuration()
        try:
            response = await client.chat.completions.create(
                model=configuration.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        finally:
            await client.close()

    async def generate_structured(
        self, system_prompt: str, user_prompt: str, response_format: dict
    ) -> dict:
        client, configuration = await self._get_client_and_configuration()
        try:
            response = await client.chat.completions.create(
                model=configuration.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=4096,
                temperature=0.3,
            )
        finally:
            await client.close()

        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}

    async def generate_embedding(self, text: str) -> List[float]:
        client, configuration = await self._get_client_and_configuration()
        try:
            response = await client.embeddings.create(
                model=configuration.embedding_model,
                input=text,
            )
            return response.data[0].embedding
        finally:
            await client.close()

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        client, configuration = await self._get_client_and_configuration()
        try:
            response = await client.embeddings.create(
                model=configuration.embedding_model,
                input=texts,
            )
            sorted_data = sorted(response.data, key=lambda item: item.index)
            return [item.embedding for item in sorted_data]
        finally:
            await client.close()

    async def chat_with_context(
        self,
        question: str,
        context: str,
        repo_name: str,
        chat_history: List[dict] | None = None,
    ) -> str:
        client, configuration = await self._get_client_and_configuration()
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

        try:
            response = await client.chat.completions.create(
                model=configuration.chat_model,
                messages=messages,
                max_tokens=4096,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        finally:
            await client.close()
