import asyncio
import subprocess
import asyncpg
from pgvector.asyncpg import register_vector
from typing import List, Tuple
from logger import logger

DATABASE_URL = "postgresql://postgres:password@localhost:5432/vectordb"

pool: asyncpg.Pool | None = None

async def init_pool():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, init=register_vector)

async def close_pool():
    await pool.close()

async def setup():

    await init_pool()

    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

async def wait_for_db():
    for _ in range(30):
        result = subprocess.run(
            ["docker", "inspect", "--format='{{.State.Health.Status}}'", "cross-encoder-db"],
            capture_output=True, text=True
        )
        if "healthy" in result.stdout:
            logger.info("Postgres container is healthy.")
            return
        await asyncio.sleep(1)
    logger.error("Postgres container did not become healthy")
    raise RuntimeError("Postgres container did not become healthy")

async def get_existing_contents() -> set[str]:
    """
    Fetch existing contents from the database to avoid duplicates.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT content FROM document_store;")
        return {row['content'] for row in rows}

async def insert_embeddings(raw_documents: list[str], embeddings_to_insert: list[list[float]]):

    async with pool.acquire() as conn:
        await conn.executemany(
            "INSERT INTO document_store (content, embedding) VALUES ($1, $2) ON CONFLICT (content) DO NOTHING;",
            list(zip(raw_documents, embeddings_to_insert)),
        )
        logger.info(f"Inserted {len(raw_documents)} documents with embeddings into the database.")

async def search_embeddings(query_embedding: list[float], top_k: int = 20) -> list[tuple[str, float]]:

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT content, (embedding <#> $1) * -1 AS similarity
            FROM document_store
            ORDER BY embedding <#> $1
            LIMIT $2;
            """,
            query_embedding,
            top_k,
        )
        results = [(r["content"], r["similarity"]) for r in rows]
        logger.info(f"Retrieved {len(results)} documents with embeddings from the database.")
        return results
