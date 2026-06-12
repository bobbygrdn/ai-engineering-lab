from openai import OpenAI
import numpy as np
import os
import re
from dotenv import load_dotenv
import argparse
import nltk
from nltk.tokenize import sent_tokenize
import uuid

nltk.download('punkt_tab')
load_dotenv()
client = OpenAI()

client.api_key= os.getenv("OPENAI_API_KEY")

def get_embeddings(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """
    Get the embedding vectors for a list of texts in a single batch call.
    """
    response = client.embeddings.create(input=texts, model=model)
    return [embedding.embedding for embedding in response.data]

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calcuate the cosine similarity between two vectors.
    """
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def split_into_units(text: str) -> list[dict]:
    """
    Splits markdown text into atomic units: headers, tables, and sentences
    """
    units = []
    blocks = text.split('\n\n')
    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        if not block:
            i += 1
            continue

        # Header + following block
        if block.startswith('#'):
            # Combine header with the next non‑empty block
            header = block
            i += 1
            while i < len(blocks) and not blocks[i].strip():
                i += 1
            if i < len(blocks):
                following = blocks[i].strip()
                combined = header + '\n\n' + following
                units.append({'type': 'header', 'text': combined})
            else:
                units.append({'type': 'header', 'text': header})
        elif block.startswith('|'):
            units.append({'type': 'table', 'text': block})
        else:
            raw_sentences = sent_tokenize(block)
            merged_sentences = []
            temp_fragment = ""


            for s in raw_sentences:
                s = s.strip()
                if not s:
                    continue

                if len(s) < 5 and (s[-1] == '.' or s.isdigit()):
                    temp_fragment += s + " "
                else:
                    # Combine any buffered fragments with the current sentence
                    full_sentence = (temp_fragment + s).strip()
                    merged_sentences.append(full_sentence)
                    temp_fragment = ""
            
            # Handle any trailing fragment at the end of the block
            if temp_fragment:
                merged_sentences.append(temp_fragment.strip())

            for s in merged_sentences:
                units.append({'type': 'text', 'text': s})
        i += 1
    return units

def semantic_chunking(text: str, threshold: float = 0.85) -> list[dict]:
    """
    Splits text into hierarchical chunks.

    Returns:
        List[dict] where each dict has:
            - parent_id: str
            - parent_text: str
            - children: List[dict] with keys:
                - child_id: str
                - text: str
                - embedding: list[float]   (optional, can be omitted if you store separately)
    """

    # Split the text into atomic units
    units = split_into_units(text)
    if not units:
        return []

    # Extract text for embedding
    unit_texts = [unit['text'] for unit in units]
    embeddings = get_embeddings(unit_texts)

    chunks = []
    current_chunk_units = [units[0]]

    # Identify breakpoints based on cosine similarity
    for i in range(len(embeddings) - 1):
        unit_current = units[i]
        unit_next = units[i + 1]

        # Force a split if the next unit is a header (structural boundary)
        if unit_next['type'] == 'header':
            chunks.append('\n\n '.join([u['text'] for u in current_chunk_units]))
            current_chunk_units = [unit_next]
            continue
    
        # Calculate similarity between current and next unit
        similarity = cosine_similarity(embeddings[i], embeddings[i + 1])

        if similarity < threshold:
            chunks.append('\n\n'.join([u['text'] for u in current_chunk_units]))
            current_chunk_units = [unit_next]
        else:
            current_chunk_units.append(unit_next)

    # Append the last chunk
    chunks.append('\n\n'.join([u['text'] for u in current_chunk_units]))

    # Convert to hierarchical structure
    hierarchical = []
    for chunk in chunks:
        # Generate a unique parent ID
        parent_id = str(uuid.uuid4())

        #Split chunk back into its constituent units (sentences, tables, headers)
        #Re-use split_into_units to maintain consistency
        units = split_into_units(chunk)

        # Get embeddings for each unit
        unit_texts = [unit['text'] for unit in units]
        unit_embeddings = get_embeddings(unit_texts)

        children = []
        for unit, embedding in zip(units, unit_embeddings):
            child_id = str(uuid.uuid4())
            children.append({
                'child_id': child_id,
                'text': unit['text'],
                'embedding': embedding
            })

        hierarchical.append({
            'parent_id': parent_id,
            'parent_text': chunk,
            'children': children
        })

    return hierarchical
