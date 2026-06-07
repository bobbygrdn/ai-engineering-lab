from tokens import count_tokens
from packer import group_neighborhoods, pack_neighborhoods
from prompt_composer import compose_system_prompt, system_overhead_tokens

MODEL_CONTEXT_LIMIT = 4096
RESPONSE_RESERVE = 512
SYSTEM_INSTRUCTIONS = (
    "You are an assistant that MUST cite evidence from 'RETRIEVED EVIDENCE'.\n"
    "If no evidence is available, say you don't know.\n"
)

def simulate_retrieval():
    chunks = []

    for i in range(4):
        chunks.append({
            "doc_id": "docA",
            "chunk_id": i,
            "text": "Document A chunk %d. " % i + "Lorem ipsum " * (50 + i*10),
            "score": 1.0 / (1 + i)
        })

    for i in range(2):
        chunks.append({
            "doc_id": "docB",
            "chunk_id": i,
            "text": "Document B chunk %d. " % i + "Dolor sit amet " * (80 - i*10),
            "score": 0.9 - i*0.1
        })

    chunks.append({
        "doc_id": "docC",
        "chunk_id": 0,
        "text": "Document C large chunk. " + "X " * 2000,
        "score": 0.6
    })
    return chunks

def main():
    query = "Explain the relationship between A and B."
    chunks = simulate_retrieval()

    overhead = system_overhead_tokens(SYSTEM_INSTRUCTIONS) + count_tokens(query)
    budget_for_retrieved = MODEL_CONTEXT_LIMIT - overhead - RESPONSE_RESERVE
    print(f"Model limit {MODEL_CONTEXT_LIMIT}, reserve {RESPONSE_RESERVE}, overhead {overhead} => budget for retrieved {budget_for_retrieved}") 

    neighborhoods = group_neighborhoods(chunks)
    selected = pack_neighborhoods(neighborhoods, budget_for_retrieved)

    total_selected_tokens = sum(n["token_count"] for n in selected)
    print(f"Selected {len(selected)} neighborhoods, tokens used by retrieved: {total_selected_tokens}")
    prompt = compose_system_prompt(SYSTEM_INSTRUCTIONS, selected)
    print("\n--- COMPOSED SYSTEM PROMPT (preview) ---\n")
    print(prompt[:2000])
    print("\n--- lengths ---")
    print("system_prompt_tokens:", count_tokens(prompt))
    print("query_tokens:", count_tokens(query))
    print("response_reserve:", RESPONSE_RESERVE)
    print("TOTAL (should be <= limit):", count_tokens(prompt) + count_tokens(query) + RESPONSE_RESERVE)

if __name__ == "__main__":
    main()