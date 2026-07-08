# vector_store.py
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer
import pandas as pd
import hashlib
from typing import Set
from logger import get_logger

logger = get_logger(__name__)

embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
client   = QdrantClient(url="http://localhost:6333")
COLLECTION = "movies_overview"


def _ensure_collection(df: pd.DataFrame) -> None:
    """Create collection if it does not exist and upsert all points."""
    try:
        client.get_collection(collection_name=COLLECTION)
        logger.info(f"Collection '{COLLECTION}' already exists.")
    except Exception:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=embedder.get_sentence_embedding_dimension(),
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.info(f"Collection '{COLLECTION}' created.")

    existing_ids = _existing_ids()

    new_rows = [
        (index, row) for index, row in enumerate(df.itertuples())
        if index not in existing_ids
    ]

    if not new_rows:
        print("No new rows to upsert.")
        logger.info("No new rows to upsert.")
        return

    new_indices   = [i for i, _ in new_rows]
    new_overviews = [
        "" if pd.isna(row.overview) else str(row.overview)
        for _, row in new_rows
    ]

    new_embeddings = embedder.encode(
        new_overviews, batch_size=64, normalize_embeddings=True
    )

    new_payloads = [
        {
            "title": row.title,
            "movie_id": int(row.id),
            "release_date": row.release_date,
            "vote_average": float(row.vote_average),
            "original_language": row.original_language,
            "overview": "" if pd.isna(row.overview) else str(row.overview),
        }
        for _, row in new_rows
    ]

    BATCH_SIZE = 500
    total = len(new_indices)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch_points = [
            qmodels.PointStruct(
                id=idx,
                vector=emb.tolist(),
                payload=payload,
            )
            for idx, emb, payload in zip(
                new_indices[start:end],
                new_embeddings[start:end],
                new_payloads[start:end],
            )
        ]
        client.upsert(collection_name=COLLECTION, points=batch_points)
        print(f"🔹 Upserted batch {start // BATCH_SIZE + 1} ({end - start} points)")
        logger.info(f"Upserted batch {start // BATCH_SIZE + 1} ({end - start} points)")

    logger.info(f"Upserted {total} new points into collection '{COLLECTION}'.")

def retrieve_similar(question: str, top_k: int = 5) -> list[dict]:
    """Return a list of dicts with keys `text` and `payload`."""
    q_vec = embedder.encode([question], normalize_embeddings=True)[0]

    hits = client.query_points(
        collection_name=COLLECTION,
        query=q_vec.tolist(),
        limit=top_k,
        with_payload=True,
    )

    results = hits.points

    return [
        {"text": hit.payload["overview"], "payload": hit.payload}
        for hit in results
    ]

def _doc_hash(text: str) -> str:
    """Return a hash of the document text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def _existing_ids() -> Set[int]:
    """
    Return a set with all point IDs that are already present in the collection.
    """
    ids = set()
    offset = None
    limit = 1000

    while True:
        response = client.scroll(
            collection_name=COLLECTION,
            limit=limit,
            offset=offset,
            with_payload=True
        )

        points, next_offset = response

        for point in points:
            ids.add(point.id)

        if next_offset is None:
            break

        offset = next_offset

    return ids