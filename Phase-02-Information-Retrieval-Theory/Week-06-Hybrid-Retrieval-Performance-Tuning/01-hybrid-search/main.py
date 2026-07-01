from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
import json, pathlib, uuid, os, datetime, json

# ----------------------------------------------------------------------
#  Load the JSON dataset
# ----------------------------------------------------------------------
data_path = pathlib.Path(
    r"c:\Users\bobby\Desktop\code\ai-engineering-lab\Phase-02-Information-Retrieval-Theory\Week-06-Hybrid-Retrieval-Performance-Tuning\01-hybrid-search\startups_demo.json"
)
with data_path.open(encoding="utf-8") as f:
    startups = json.load(f)

# ----------------------------------------------------------------------
#  Initialise Qdrant client and the embedding model
# ----------------------------------------------------------------------
client = QdrantClient(url="http://localhost:6333")
model  = SentenceTransformer("all-MiniLM-L6-v2")   # 384‑dim model

# ----------------------------------------------------------------------
#  Deterministic UUID helper (stable across runs)
# ----------------------------------------------------------------------
def deterministic_id(record: dict) -> str:
    """
    Returns a stable UUID derived from the record’s textual fields.
    Uses UUID‑5 (SHA‑1) with the DNS namespace.
    """
    parts = [
        record.get("name", ""),
        record.get("description", ""),
        record.get("city", ""),
    ]
    name = "|".join(parts)
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

# ----------------------------------------------------------------------
#  Convert a raw record into the payload we store (adds a stable id)
# ----------------------------------------------------------------------
def make_document(record):
    txt = f"{record.get('name','')} {record.get('description','')} {record.get('city','')}"
    return {
        "id": deterministic_id(record),   # <-- stable id
        "text": txt
    }

# ----------------------------------------------------------------------
#  Build the list of documents (payloads)
# ----------------------------------------------------------------------
docs = [make_document(rec) for rec in startups]

# ----------------------------------------------------------------------
#  Create the hybrid collection (dense + sparse config for BM25)
# ----------------------------------------------------------------------
if not client.collection_exists("hybrid_collection"):
    client.create_collection(
        collection_name="hybrid_collection",
        vectors_config={
            "dense": models.VectorParams(
                size=384,
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                modifier=models.Modifier.IDF,
            )
        },
    )

# ----------------------------------------------------------------------
#  Encode all documents with the dense model
# ----------------------------------------------------------------------
texts = [d["text"] for d in docs]
dense_vectors = model.encode(texts, batch_size=64).tolist()

# ----------------------------------------------------------------------
#  Get the set of IDs that already exist in the collection
# ----------------------------------------------------------------------
def get_existing_ids(collection_name: str) -> set[str]:
    ids = set()
    offset = None
    limit = 1000

    while True:
        response = client.scroll(
        collection_name=collection_name,
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

existing_ids = get_existing_ids("hybrid_collection")

# ----------------------------------------------------------------------
#  Build only the points that are *new* (or have changed)
# ----------------------------------------------------------------------
points_to_upload = []
for doc, dense_vec in zip(docs, dense_vectors):
    if doc["id"] in existing_ids:
        # Already present – skip it
        continue

    points_to_upload.append(
        models.PointStruct(
            id=doc["id"],
            vector={"dense": dense_vec},   # only dense vector stored
            payload=doc,
        )
    )

# ----------------------------------------------------------------------
#  Upload the new points (if any)
# ----------------------------------------------------------------------
if points_to_upload:
    client.upload_points(
        collection_name="hybrid_collection",
        points=points_to_upload,
    )
    print(f"Uploaded {len(points_to_upload)} new points.")
else:
    print("No new points to upload – collection already contains all documents.")

# ----------------------------------------------------------------------
#  Hybrid search (RRF fusion) – dense + on‑the‑fly BM25
# ----------------------------------------------------------------------
def hybrid_search(query: str, top_k: int = 10):
    # Dense embedding of the query
    dense_vec = model.encode([query])[0].tolist()

    prefetch = [
        models.Prefetch(
            query=models.Document(text=query, model="Qdrant/bm25"),
            using="sparse",
            limit=top_k,
        ),
        models.Prefetch(
            query=dense_vec,
            using="dense",
            limit=top_k,
        ),
    ]

    fusion_query = models.FusionQuery(fusion=models.Fusion.RRF)

    response = client.query_points(
        collection_name="hybrid_collection",
        prefetch=prefetch,
        query=fusion_query,
        limit=top_k,
        with_payload=True,
    )
    return response.points

# ----------------------------------------------------------------------
#  Helper: write the hybrid‑search results of the current run to a log file
# ----------------------------------------------------------------------
def write_run_log(query: str, top_k: int, results: list):
    """
    Append a JSON‑line record to `results/hybrid_search.log`.
    Each line represents one execution of the script.
    """
    # Ensure the folder exists
    os.makedirs("results", exist_ok=True)

    # Build a compact representation of the results
    result_items = []
    for pt in results:
        result_items.append({
            "id": pt.id,
            "score": pt.score,
            "text": pt.payload.get("text", "")
        })

    utc_now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    log_entry = {
        "run_id": f"{utc_now}_{uuid.uuid4().hex[:8]}",
        "timestamp": utc_now,
        "query": query,
        "top_k": top_k,
        "results": result_items
    }

    log_path = os.path.join("results", "hybrid_search.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n" + "---" + "\n")

# ----------------------------------------------------------------------
#  Run a sample query
# ----------------------------------------------------------------------
if __name__ == "__main__":
    query = "web-based startups in Chicago"
    top_k = 10 # Optional: specify how many results to retrieve, default is 10
    
    hybrid_results = hybrid_search(query, top_k=top_k)

    write_run_log(query, top_k, hybrid_results)