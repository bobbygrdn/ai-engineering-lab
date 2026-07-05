from openai import OpenAI
import os
from dotenv import load_dotenv
from typing import List, Tuple
from logger import logger

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI()
client.api_key = OPENAI_API_KEY

def generate_response(query: str, top_results: list[tuple[str, float]]) -> str:
    context = "\n\n".join([f"Result {i+1}: {text}" for i, (text, score) in enumerate(top_results)])
    prompt = f"Context:\n{context}\n\nPlease provide a concise and accurate response to the user's query based on the provided context."

    response = client.responses.create(
        model="gpt-4o-mini",
        instructions=prompt,
        input=query,
    )

    logger.info(f"Generated response for query: {query}")
    logger.info(f"Top results used for response generation: {top_results}")
    logger.info(f"LLM response: {response.output_text}")
    return response.output_text


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    BATCH_SIZE = 2048

    embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        embeddings.extend([e.embedding for e in response.data])
        logger.info(f"Generated embeddings for batch of size {len(batch)}")
    return embeddings

def embed_query(query: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    logger.info(f"Generated embedding for query: {query}")
    return response.data[0].embedding