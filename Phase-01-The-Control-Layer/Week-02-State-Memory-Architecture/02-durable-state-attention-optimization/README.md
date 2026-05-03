# Part 2: Durable State & Attention Optimization

## Terms

- Durable State
- Hydration / Hydrated
- Mind (as a data structure)
- Typed Memories (Preferences, Past Issues, System Context)
- SQLite / JSON schema
- State Bridge
- Structural Assembly rule
- Attention Peaks (top/bottom of prompt)
- Low-Attention zone (middle of prompt)
- Write-Back
- Probabilistic Recall
- Prompt Jockey
- Dangerous Engineer
- Attention Architecting

## Key Concepts

- Persistence: Storing state in a durable, queryable format (SQLite/JSON).
- Memory Typing: Categorizing memories for targeted retrieval and update.
- Hydration: Loading stored state into a working memory or prompt context.
- Attention Optimization: Placing information in a prompt to maximize LLM recall, leveraging the model’s bias toward sequence edges.
- Structural Assembly: Systematic arrangement of prompt content by priority.
- Write-Back Loop: Updating persistent state with new facts after inference.
- Probabilistic Recall: Understanding and exploiting the LLM’s attention distribution for reliable information retrieval.

## Implementation Overview

This project implements a memory-augmented LLM prompt system with the following primary capabilities:

- Persistent storage of "typed memories" (preferences, past issues, system context) in a JSON file.
- Hydration: Loading and prioritizing memories by recency.
- Attention optimization: Assembling prompts to place high-priority information at the top/bottom (Attention Peaks) and less critical data in the middle (Low-Attention Zone).
- Write-back: Parsing LLM responses and updating persistent state.
- Probabilistic recall: Using recency and type to maximize LLM retrieval reliability.

## How It Works

1. **Startup** : The main script loads environment variables and ensures the memories.json file exists.
2. **User Input** : The user provides a message for the LLM.
3. **Hydration** : The system loads and prioritizes memories from the JSON file, sorting by timestamp.
4. **Prompt Assembly** : The prompt is constructed, placing preferences and system context at the edges, and past issues in the middle.
5. **LLM Call** : The prompt is sent to the LLM (via OpenAI API).
6. **Write-Back** : The LLM response is parsed and appended as a new "past issue" in the persistent memory file.
7. **Logging** : All interactions are logged for traceability.

## Example Usage

```
# Example: Running the main workflow
# (from src/main.py)
if __name__ == "__main__":
    main()
```

```
# Example: Generating large test data
# (from test/generate_test_data.py)
with open("memories.json", "w") as f:
    json.dump(large_memories, f, indent=2)
```

## Next Steps

- Implement more advanced memory retrieval (e.g., semantic search, embedding-based recall).
- Add support for SQLite as a backend for scalable, queryable state.
- Enhance the prompt assembly logic to dynamically adjust attention zones based on LLM context window.
- Integrate more robust error handling and schema validation.
- Track and visualize attention distribution and recall metrics for continuous optimization.
