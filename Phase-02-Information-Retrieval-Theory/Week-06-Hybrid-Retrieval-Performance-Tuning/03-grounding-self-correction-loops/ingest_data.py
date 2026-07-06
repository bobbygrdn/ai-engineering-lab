from llm import generate_embeddings
from vector_store import setup, insert_embeddings, wait_for_db, close_pool, get_existing_contents
from data_ingestion import get_clean_texts
import asyncio
from logger import logger

async def populate_database(raw_documents: list[str]) -> None:
    # generate embeddings (sync call)
    embeddings = generate_embeddings(raw_documents)

    # bulk insert
    await insert_embeddings(raw_documents, embeddings)

async def main() -> None:
     # DB schema & pool
    await wait_for_db()
    await setup()

    # Load & clean data
    texts = get_clean_texts()

    # Check for existing contents to avoid duplicates
    existing_contents = await get_existing_contents()

    # Filter out new texts that are not already in the database
    new_texts = [text for text in texts if text not in existing_contents]

    # If there are new texts, populate the database, otherwise log that there are no new documents
    if not new_texts:
        logger.info("No new documents to ingest.")
        print("No new documents to ingest.")
    else:
        await populate_database(new_texts)
        logger.info(f"Inserted {len(new_texts)} new documents into the database.")
        print(f"Inserted {len(new_texts)} new documents into the database.")

    # Clean shutdown
    await close_pool()
    logger.info("Database connection closed.")

if __name__ == "__main__":
    asyncio.run(main())