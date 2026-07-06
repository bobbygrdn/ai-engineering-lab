import asyncio
import os
from llm import generate_response, embed_query
from vector_store import setup, wait_for_db, search_embeddings
from functools import lru_cache
from logger import logger
import logging

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"
# Ensure the HuggingFace hub operates online on first run so the model can be downloaded.
os.environ["HF_HUB_OFFLINE"] = "0"
HF_CACHE_DIR = os.path.expanduser("cache/huggingface")
os.makedirs(HF_CACHE_DIR, exist_ok=True)

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

@lru_cache(maxsize=1)
def get_cross_encoder():
    from sentence_transformers import CrossEncoder
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id="cross-encoder/ms-marco-MiniLM-L12-v2",
        cache_dir=HF_CACHE_DIR,
        local_files_only=False,
    )
    return CrossEncoder(
        "cross-encoder/ms-marco-MiniLM-L12-v2",
        device="cpu",
        cache_folder=HF_CACHE_DIR
    )

resources_ready = asyncio.Event()

async def init_db():
    await wait_for_db()
    await setup()

async def load_cross_encoder():
    await asyncio.to_thread(get_cross_encoder)

async def await_resources():
    try:
        await asyncio.gather(init_db(), load_cross_encoder())
        # After successful caching we can safely enforce offline mode for subsequent runs.
        os.environ["HF_HUB_OFFLINE"] = "1"
        logger.info("Offline mode enabled after successful caching.")
    except Exception as e:
        logger.error(f"Error occurred while awaiting resources: {e}")
    finally:
        resources_ready.set()
        logger.info("All resources are ready (or attempted).")

async def chat() -> None:
    print("=== How may I help you today? (type 'exit' to quit) ===")
    while True:
        query = input("You: ").strip()
        if query.lower() in {"exit", "quit"}:
            break
        if not resources_ready.is_set():
            print("Waiting for resources to be ready...")
            await resources_ready.wait()

        # Embed the query
        query_emb = embed_query(query)

        # Fast vector retrieval (top‑20)
        candidates = await search_embeddings(query_emb, top_k=20)

        if not candidates:
            print("Bot: No relevant documents found.")
            continue

        # Cross‑encoder re‑ranking
        pairs = [(query, doc) for doc, _ in candidates]
        scores = get_cross_encoder().predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

        # Keep best 3 for LLM context
        top_texts = [doc for (doc, _), _ in ranked[:3]]
        top_scores = [score for _, score in ranked[:3]]

        # Generate answer
        llm_reply = generate_response(query, list(zip(top_texts, top_scores)))
        print(f"Bot: {llm_reply}")

async def main() -> None:
    asyncio.create_task(await_resources())
    await chat()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")