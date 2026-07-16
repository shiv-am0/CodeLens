from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from loguru import logger
import json

from app.models.repository import RepositoryFile
from app.services.openai_service import OpenAIService


class EmbeddingService:
    def __init__(self, db: AsyncSession, openai_service: OpenAIService):
        self.db = db
        self.openai = openai_service

    def chunk_file(self, content: str, path: str, max_chunk_size: int = 1000) -> List[str]:
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            line_size = len(line) // 4
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append(f"File: {path}\n" + "\n".join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size

        if current_chunk:
            chunks.append(f"File: {path}\n" + "\n".join(current_chunk))

        return chunks

    async def generate_and_store_embeddings(self, repository_id: int) -> int:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = list(result.scalars().all())
        total_chunks = 0

        for file in files:
            if not file.content:
                continue
            chunks = self.chunk_file(file.content, file.path)
            for chunk in chunks:
                try:
                    embedding = await self.openai.generate_embedding(chunk)
                    embedding_json = json.dumps(embedding)
                    stmt = text("""
                        UPDATE repository_files
                        SET embedding = :embedding
                        WHERE id = :file_id
                    """)
                    await self.db.execute(stmt, {"embedding": embedding_json, "file_id": file.id})
                    total_chunks += 1
                except Exception as e:
                    logger.error(f"Embedding failed for {file.path}: {e}")

        await self.db.commit()
        logger.info(f"Generated {total_chunks} embeddings for repository {repository_id}")
        return total_chunks

    async def search_similar(self, repository_id: int, query: str, top_k: int = 10) -> List[dict]:
        query_embedding = await self.openai.generate_embedding(query)
        query_embedding_json = json.dumps(query_embedding)

        stmt = text("""
            SELECT id, path, content,
                   1 - (cosine_distance(
                       embedding::vector,
                        CAST(:query AS vector)
                   )) as similarity
            FROM repository_files
            WHERE repository_id = :repo_id
              AND embedding IS NOT NULL
            ORDER BY similarity DESC
            LIMIT :top_k
        """)
        result = await self.db.execute(
            stmt,
            {"query": query_embedding_json, "repo_id": repository_id, "top_k": top_k},
        )
        rows = result.all()
        return [
            {"id": r[0], "path": r[1], "content": r[2][:2000] if r[2] else "", "similarity": float(r[3])}
            for r in rows
        ]

    async def get_context_for_chat(self, repository_id: int, question: str) -> str:
        similar_docs = await self.search_similar(repository_id, question, top_k=10)
        context_parts = []
        for doc in similar_docs:
            context_parts.append(f"--- {doc['path']} (relevance: {doc['similarity']:.2f}) ---\n{doc['content']}")
        return "\n\n".join(context_parts)
