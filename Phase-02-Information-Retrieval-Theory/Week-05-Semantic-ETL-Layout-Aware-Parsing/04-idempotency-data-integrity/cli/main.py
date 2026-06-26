"""
Interactive Semantic Chunking & Retrieval CLI

The menu is intentionally simple – it uses only the standard library
(`input()`, `print()`) so it works in any terminal.  If you want a fancier
UI you can replace the `prompt_*` helpers with `prompt_toolkit` or
`curses` later.

Usage:

    python -m cli.main

"""

import json
import os
import sys
from pathlib import Path

from utils.embeddings import semantic_chunking, get_embeddings
from utils.datastore import (
    store_vectors,
    search,
    get_parent_texts,
    create_collection,
)
from utils.process_single_document import parse_pdf_to_markdown
from utils.llm import ask, create_metadata


# --------------------------------------------------------------------------- #
# 1.  Helper functions
# --------------------------------------------------------------------------- #
def _load_hierarchy(json_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_hierarchy(hierarchy, json_path: str):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(hierarchy, f, ensure_ascii=False, indent=2)

def _prompt_file(prompt: str, must_exist: bool = True) -> str:
    while True:
        path = input(prompt).strip()
        if not path:
            print("  (empty → cancel)")
            return ""
        if must_exist and not os.path.exists(path):
            print("  File does not exist. Try again.")
            continue
        return path

def _prompt_float(prompt: str, default: float) -> float:
    val = input(f"{prompt} [{default}]: ").strip()
    return float(val) if val else default

def _prompt_int(prompt: str, default: int) -> int:
    val = input(f"{prompt} [{default}]: ").strip()
    return int(val) if val else default


# --------------------------------------------------------------------------- #
# 2.  Menu actions
# --------------------------------------------------------------------------- #
def action_convert_pdf():
    pdf = _prompt_file("PDF path: ")
    if not pdf:
        return
    output = parse_pdf_to_markdown(pdf)
    print(f"Markdown written to {output}")

def action_chunk():
    md = _prompt_file("Markdown file to chunk: ")
    if not md:
        return
    threshold = _prompt_float("Similarity threshold", 0.7)
    hierarchy = semantic_chunking(
        open(md, encoding="utf-8").read(), threshold=threshold
    )
    print(f"Created {len(hierarchy)} parent chunks.")
    out = _prompt_file("Save hierarchy to JSON? (leave empty to skip): ", must_exist=False)
    if out:
        _save_hierarchy(hierarchy, out)
        print(f"Hierarchy saved to {out}")

def action_create_metadata_for_chunk():
    chunk = input("Enter the chunk text: ").strip()
    if not chunk:
        return
    metadata = create_metadata(chunk)
    print(f"Created metadata for chunk:\n{metadata}")

def action_store():
    coll = input("Collection name [02-semantic-chunking]: ").strip() or "02-semantic-chunking"
    inp = _prompt_file("JSON hierarchy file (leave empty to re‑chunk): ", must_exist=False)
    if inp:
        hierarchy = _load_hierarchy(inp)
    else:
        md = _prompt_file("Markdown file to chunk: ")
        if not md:
            return
        threshold = _prompt_float("Similarity threshold", 0.7)
        hierarchy = semantic_chunking(
            open(md, encoding="utf-8").read(), threshold=threshold
        )
    store_vectors(coll, hierarchy)
    print(f"Vectors stored in collection '{coll}'.")

    file_path = Path(inp)
    file_path.unlink(missing_ok=True)
    print(f"Deleted hierarchy file {inp}.")

def action_search():
    coll = input("Collection name [02-semantic-chunking]: ").strip() or "02-semantic-chunking"
    query = input("Search query: ").strip()
    if not query:
        return
    k = _prompt_int("Top‑k hits", 5)
    hits = search(query, coll, top_k=k)
    if not hits:
        print("No hits found.")
        return
    parents = get_parent_texts(hits, coll)
    print(f"\nFound {len(hits)} child hits, {len(parents)} unique parents.\n")
    for pid, txt in parents.items():
        print(f"\n--- Parent {pid} ---\n{txt}\n")

def action_ask():
    coll = input("Collection name [02-semantic-chunking]: ").strip() or "02-semantic-chunking"
    question = input("Your question: ").strip()
    if not question:
        return
    k = _prompt_int("Top‑k child hits to consider", 5)
    print("Generating hypothetical answer...")
    hypothetical_answer = generate_hypothetical_answer(question)
    hits = search(hypothetical_answer, coll, top_k=k)
    if not hits:
        print("No relevant context found.")
        return
    parents = get_parent_texts(hits, coll)
    contexts = list(parents.values())
    answer = ask(question, contexts)
    print("\nAnswer:\n")
    print(answer)

# --------------------------------------------------------------------------- #
# 3.  Main loop
# --------------------------------------------------------------------------- #
def main():
    actions = {
        "1": ("Convert PDF → Markdown", action_convert_pdf),
        "2": ("Chunk Markdown file", action_chunk),
        "3": ("Create metadata for chunk", action_create_metadata_for_chunk),
        "4": ("Store vectors in Qdrant", action_store),
        "5": ("Search vector store", action_search),
        "6": ("Ask a question (search + LLM)", action_ask),
        "q": ("Quit", None),
    }

    while True:
        print("\n=== Semantic Chunking CLI ===")
        for key, (desc, _) in actions.items():
            print(f"  {key}. {desc}")
        choice = input("Select an option: ").strip().lower()

        if choice == "q":
            print("Good‑bye!")
            break

        action = actions.get(choice)
        if not action:
            print("Invalid choice – try again.")
            continue

        try:
            action[1]()  # call the function
        except Exception as exc:
            print(f"Error: {exc}")

if __name__ == "__main__":
    main()