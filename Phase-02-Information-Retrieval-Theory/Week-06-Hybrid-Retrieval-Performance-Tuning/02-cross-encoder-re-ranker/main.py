import asyncio
from llm import generate_response, embed_query, generate_embeddings
from vector_store import setup, insert_embeddings, search_embeddings, close_pool, wait_for_db
from data_ingestion import get_clean_texts
from sentence_transformers import CrossEncoder

cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2")

async def populate_database(raw_documents: list[str]) -> None:
    # generate embeddings (sync call)
    embeddings = generate_embeddings(raw_documents)

    # bulk insert
    await insert_embeddings(raw_documents, embeddings)

async def chat() -> None:
    print("=== How may I help you today? (type 'exit' to quit) ===")
    while True:
        query = input("You: ").strip()
        if query.lower() in {"exit", "quit"}:
            break

        # Embed the query
        query_emb = embed_query(query)

        # Fast vector retrieval (top‑20)
        candidates = await search_embeddings(query_emb, top_k=20)

        if not candidates:
            print("Bot: No relevant documents found.")
            continue

        # Cross‑encoder re‑ranking
        pairs = [(query, doc) for doc, _ in candidates]
        scores = cross_encoder.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

        # Keep best 3 for LLM context
        top_texts = [doc for (doc, _), _ in ranked[:3]]
        top_scores = [score for _, score in ranked[:3]]

        # Generate answer
        llm_reply = generate_response(query, list(zip(top_texts, top_scores)))
        print(f"Bot: {llm_reply}")

async def main_entry() -> None:
    # DB schema & pool
    await wait_for_db()
    await setup()

    # Load & clean data, then ingest
    texts = get_clean_texts()
    await populate_database(texts)

    # Interactive chat
    await chat()

    # Clean shutdown
    await close_pool()

if __name__ == "__main__":
    try:
        asyncio.run(main_entry())
    except KeyboardInterrupt:
        print("\nGoodbye!")