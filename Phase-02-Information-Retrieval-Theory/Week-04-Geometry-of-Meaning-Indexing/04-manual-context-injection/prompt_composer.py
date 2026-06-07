from tokens import count_tokens

SYSTEM_WRAPPER = (
    "You are a helpful assistant. Use the following retrieved evidence to answer the user's query.\n\n"
    "RETRIEVED EVIDENCE:\n"
    "===================\n"
)

ANSWER_DIRECTIVE = (
    "Answer the user's question directly from the retrieved evidence. "
    "If the evidence supports a cause or explanation, state it plainly and cite the source ids. "
    "Only say you don't know when the retrieved evidence is actually insufficient."
)

def compose_system_prompt(system_instructions: str, selected_neighborhoods) -> str:
    parts = [system_instructions, ANSWER_DIRECTIVE, "\n"]
    for n in selected_neighborhoods:
        for chunk in n["chunks"]:
            header = f"[Source: {n['doc_id']} | chunk: {chunk['chunk_id']}]"
            parts.append(header)
            parts.append(chunk["text"])
            parts.append("\n---\n")
    return "\n".join(parts)

def system_overhead_tokens(system_instructions: str) -> int:
    return count_tokens(system_instructions)