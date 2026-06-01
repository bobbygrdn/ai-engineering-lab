from pinecone import Pinecone, ServerlessSpec
import os
from dotenv import load_dotenv
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timezone
import csv
import time
import uuid

"""
Run this script to execute the experiment and generate `pinecone_per_query.csv` and `pinecone_results.csv` in the current directory. Then run `analyze_results.py` to analyze and visualize the results.

Requires: pinecone-client, scikit-learn, python-dotenv

Set up a `.env` file with your Pinecone API key and index name, e.g.:
PINECONE_API_KEY=your_api_key_here
INDEX_NAME=your_index_name_here

Optionally, you can set experiment parameters via environment variables in the `.env` file, e.g.:
DIMENSION=128
NUM_VECTORS=10000
NUM_QUERIES=100
K=10
BATCH_SIZE=1000
WARMUP=20
TRIALS=3
PER_QUERY_CSV=pinecone_per_query.csv
RESULTS_FILE=pinecone_results.csv
CREATE_INDEX_PER_COMBO=false
"""

load_dotenv()

client = Pinecone(
    api_key=os.getenv("PINECONE_API_KEY"),
)

index_name = os.getenv("INDEX_NAME")

if not index_name:
    raise RuntimeError("INDEX_NAME environment variable is not set. Please set it in the .env file.")

# Experiment config (override via env)
dim = int(os.getenv("DIMENSION", "128"))
N = int(os.getenv("NUM_VECTORS", "10000"))
Q = int(os.getenv("NUM_QUERIES", "100"))
K = int(os.getenv("K", "10"))
batch_size = int(os.getenv("BATCH_SIZE", "1000"))
WARMUP = int(os.getenv("WARMUP", "20"))
TRIALS = int(os.getenv("TRIALS", "3"))
PER_QUERY_FILE = os.getenv("PER_QUERY_CSV", "pinecone_per_query.csv")
RESULTS_FILE = os.getenv("RESULTS_FILE", "pinecone_results.csv")

if index_name not in client.list_indexes().names():
    client.create_index(
        name=index_name,
        dimension=dim,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
index = client.Index(index_name)

# synthesize data
X = np.random.normal(size=(N, dim)).astype(np.float32)
X /= np.linalg.norm(X, axis=1, keepdims=True)
queries = X[np.random.choice(N, Q, replace=False)]

# ground-truth via brute-force cosine similarity
sims = cosine_similarity(queries, X)
gt = np.argsort(-sims, axis=1)[:, :K]

# upsert vectors (id = string index) and measure build time for base index
batch = []
base_build_time_s = None
base_vector_count = None
start_upsert = time.perf_counter()
for i, vec in enumerate(X):
    batch.append((str(i), vec.tolist()))
    if len(batch) >= batch_size:
        index.upsert(vectors=batch)
        batch = []
if batch:
    index.upsert(vectors=batch)
end_upsert = time.perf_counter()
base_build_time_s = end_upsert - start_upsert
# try to read vector count for base index
try:
    stats = index.describe_index_stats()
    if isinstance(stats, dict):
        if 'totalVectorCount' in stats:
            base_vector_count = int(stats.get('totalVectorCount') or 0)
        elif 'total_vector_count' in stats:
            base_vector_count = int(stats.get('total_vector_count') or 0)
        elif 'namespaces' in stats:
            # sum vector_count inside namespaces if present
            try:
                base_vector_count = int(sum(ns.get('vector_count', 0) for ns in stats['namespaces'].values()))
            except Exception:
                base_vector_count = None
    else:
        base_vector_count = None
except Exception:
    base_vector_count = None
# small pause to allow index to settle
time.sleep(2.0)

run_id = uuid.uuid4().hex

# sweep configuration: HNSW params to try (defaults reflect lab plan)
Ms = [8, 16, 32]
efConstructions = [100, 200, 500]
efs = [10, 50, 100, 500]

# If CREATE_INDEX_PER_COMBO is true, the script will create a separate index per combo
# (useful when the provider supports different HNSW/index params per index). Default: false
CREATE_INDEX_PER_COMBO = os.getenv("CREATE_INDEX_PER_COMBO", "false").lower() in ("1", "true", "yes")

# helper: create index (if missing) and upsert dataset; returns (build_time_s, vector_count_or_none)
def create_and_upsert(idx_name):
    start = time.perf_counter()
    if idx_name not in client.list_indexes().names():
        client.create_index(
            name=idx_name,
            dimension=dim,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
    idx = client.Index(idx_name)
    # upsert all vectors in batches
    b = []
    for i, vec in enumerate(X):
        b.append((str(i), vec.tolist()))
        if len(b) >= batch_size:
            idx.upsert(vectors=b)
            b = []
    if b:
        idx.upsert(vectors=b)
    # small pause
    time.sleep(1.0)
    build_time = time.perf_counter() - start
    # try to get vector count if supported
    vector_count = None
    try:
        stats = idx.describe_index_stats()
        # API may return different keys depending on SDK; try common ones
        vector_count = stats.get("totalVectorCount") or stats.get("total_vector_count") or stats.get("total_vector_count")
    except Exception:
        try:
            # older SDKs may return a dict with namespaces
            stats = idx.describe_index_stats()
            vector_count = stats
        except Exception:
            vector_count = None
    return build_time, vector_count

# prepare per-query CSV header if needed
per_query_exists = os.path.exists(PER_QUERY_FILE)
with open(PER_QUERY_FILE, "a" if per_query_exists else "w", newline="") as pqf:
    pq_writer = csv.DictWriter(pqf, fieldnames=[
        "timestamp_utc", "run_id", "trial_id", "query_id", "latency_ms", "num_matches", "recall_at_k",
        "M", "ef_construction", "ef_search", "combo_index"
    ])
    if not per_query_exists:
        pq_writer.writeheader()

# sweep over parameter grid
for M in Ms:
    for efc in efConstructions:
        for ef in efs:
            combo_id = f"M{M}_efc{efc}_ef{ef}"
            combo_index = index_name
            build_time_s = None
            vector_count = None

            if CREATE_INDEX_PER_COMBO:
                combo_index = f"{index_name}-{combo_id}"
                # create and upsert this combo index (if not present)
                build_time_s, vector_count = create_and_upsert(combo_index)
            else:
                # no per-combo index creation; assume existing `index` contains the data
                combo_index = index_name
                # use measured base build time / vector count when available
                build_time_s = base_build_time_s
                vector_count = base_vector_count

            idx = client.Index(combo_index)

            # warm-up (not timed)
            warmup_idxs = np.random.choice(len(queries), min(WARMUP, len(queries)), replace=False)
            for wi in warmup_idxs:
                _ = idx.query(vector=queries[wi].tolist(), top_k=K, include_values=False)

            # run measured trials for this combo
            for trial in range(1, TRIALS + 1):
                latencies = []
                results = []

                with open(PER_QUERY_FILE, "a", newline="") as pqf:
                    pq_writer = csv.DictWriter(pqf, fieldnames=[
                        "timestamp_utc", "run_id", "trial_id", "query_id", "latency_ms", "num_matches", "recall_at_k", "M", "ef_construction", "ef_search", "combo_index"
                    ])

                    for qi, q in enumerate(queries):
                        t0 = time.perf_counter()
                        resp = idx.query(
                            vector=q.tolist(),
                            top_k=K,
                            include_values=False,
                        )
                        t1 = time.perf_counter()
                        latency_ms = (t1 - t0) * 1000.0
                        latencies.append(latency_ms)

                        ids = [m["id"] for m in resp.matches]
                        results.append(ids)

                        # compute per-query recall@K against ground truth
                        gt_ids = gt[qi]
                        recall_at_k = len(set(ids) & set(map(str, gt_ids))) / K

                        pq_writer.writerow({
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "run_id": run_id,
                            "trial_id": trial,
                            "query_id": qi,
                            "latency_ms": float(latency_ms),
                            "num_matches": len(ids),
                            "recall_at_k": float(recall_at_k),
                            "M": M,
                            "ef_construction": efc,
                            "ef_search": ef,
                            "combo_index": combo_index,
                        })

                # compute recall@K for this trial
                recalls = []
                for res, gt_ids in zip(results, gt):
                    recall = len(set(res) & set(map(str, gt_ids))) / K
                    recalls.append(recall)

                lat_arr = np.array(latencies)
                summary = {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "trial_id": trial,
                    "index_name": combo_index,
                    "M": M,
                    "ef_construction": efc,
                    "ef_search": ef,
                    "dimension": dim,
                    "num_vectors": N,
                    "num_queries": Q,
                    "k": K,
                    "build_time_s": build_time_s,
                    "index_vector_count": vector_count,
                    "average_latency_ms": float(np.mean(lat_arr)),
                    "p95_latency_ms": float(np.percentile(lat_arr, 95)),
                    "p99_latency_ms": float(np.percentile(lat_arr, 99)),
                    "average_recall_at_k": float(np.mean(recalls)),
                }

                print(f"[combo {combo_id} trial {trial}] avg {summary['average_latency_ms']:.2f} ms p95 {summary['p95_latency_ms']:.2f} ms p99 {summary['p99_latency_ms']:.2f} ms recall@{K} {summary['average_recall_at_k']:.4f}")

                # append trial-level summary to results CSV
                results_exists = os.path.exists(RESULTS_FILE)
                with open(RESULTS_FILE, "a" if results_exists else "w", newline="") as rf:
                    writer = csv.DictWriter(rf, fieldnames=summary.keys())
                    if not results_exists:
                        writer.writeheader()
                    writer.writerow(summary)