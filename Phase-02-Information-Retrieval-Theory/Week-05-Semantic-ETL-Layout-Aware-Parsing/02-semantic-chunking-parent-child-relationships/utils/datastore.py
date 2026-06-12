import sqlite3
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from utils.embeddings import get_embeddings


client = QdrantClient(url="http://localhost:6333")
DB_PATH = "parents.db"

def _init_db():
    """Initialize the SQLite database and create the parents table."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS parents ("
            "parent_id TEXT PRIMARY KEY, "
            "collection_name TEXT, "
            "parent_text TEXT)"
        )
        conn.commit()

def _save_parents_sqlite(collection_name: str, parents: dict[str, str]):
    """Saves parent texts to the SQLite database."""
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        # Use REPLACE to update existing parents if the same ID is used
        data = [(pid, collection_name, text) for pid, text in parents.items()]
        conn.executemany(
            "INSERT OR REPLACE INTO parents (parent_id, collection_name, parent_text) VALUES (?, ?, ?)",
            data
        )
        conn.commit()

def _load_parents_sqlite(collection_name: str, parent_ids: set[str]) -> dict[str, str]:
    """Retrieves parent texts from SQLite for a given set of IDs."""
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        # Use a parameterized query to avoid SQL injection
        placeholders = ','.join(['?'] * len(parent_ids))
        query = f"SELECT parent_id, parent_text FROM parents WHERE collection_name = ? AND parent_id IN ({placeholders})"
        
        cursor = conn.execute(query, [collection_name, *parent_ids])
        return {row[0]: row[1] for row in cursor.fetchall()}

# Create a collection for storing vectors
def create_collection(collection_name: str, vector_size: int):
    """
    Creates a collection in Qdrant with the specified name and vector size.
    """
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config={
            "size": vector_size,
            "distance": "Cosine"
        }
    )

# Upsert child embeddings into the collection
def insert_vectors(collection_name: str, vectors: list, payloads: list, child_ids: list):
    """
    Inserts vectors and their corresponding payloads into the specified collection.
    """
    client.upsert(
        collection_name=collection_name,
        points=[
            {
                "id": child_id,
                "vector": vector,
                "payload": payload
            }
            for child_id, (vector, payload) in zip(child_ids, zip(vectors, payloads))
        ]
    )

def store_vectors(collection_name: str, hierarchical: list[dict]):
    """
    High-level function to create a collection, insert vectors, and store parents in SQLite.
    """
    vectors = []
    payloads = []
    child_ids = []
    parents = {}

    for parent in hierarchical:
        parents[parent["parent_id"]] = parent["parent_text"]
        for child in parent["children"]:
            vectors.append(child["embedding"])
            payloads.append({
                "parent_id": parent["parent_id"],
                "text": child["text"]
            })
            child_ids.append(child["child_id"])

    if not client.collection_exists(collection_name):
        create_collection(collection_name, 1536)
    
    try:
        insert_vectors(collection_name, vectors, payloads, child_ids)
        _save_parents_sqlite(collection_name, parents)
        print(f"Inserted {len(vectors)} vectors and stored {len(parents)} parents in SQLite.")
    except Exception as e:
        print(f"Error occurred while storing data: {e}")

def search(query: str, collection_name: str, top_k: int = 5):
    """
    Searches for the most similar vectors in the specified collection.
    """
    query_embedding = get_embeddings([query])[0]
    try:
        search_result = client.query_points(
            collection_name=collection_name,
            query=query_embedding,
            limit=top_k,
            with_payload=True
        )
        # Return the points list from the QueryResponse object
        return search_result.points
    except Exception as e:
        print(f"Error occurred during search: {e}")
        return []

def get_parent_texts(hits, collection_name: str):
    """
    Retrieves the parent texts for the given search hits from SQLite.
    """
    if not hits:
        return {}
    
    parent_ids = {hit.payload["parent_id"] for hit in hits}
    return _load_parents_sqlite(collection_name, parent_ids)