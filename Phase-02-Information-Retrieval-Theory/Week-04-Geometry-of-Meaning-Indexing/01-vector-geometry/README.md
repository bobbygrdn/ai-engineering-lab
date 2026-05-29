# Part 1: Vector Geometry

## Terms

- Embeddings
- OpenAI API
- Sentence vectors
- Cosine similarity
- Dot product
- Vector norm
- Dimensionality
- Trigonometry
- Euclidean intuition
- Computational cost
- Semantic similarity

## Key Concepts

- Distance vs. similarity: two vectors can be far apart in raw coordinates yet still point in a similar direction.
- Direction matters more than magnitude for cosine similarity, because normalization removes scale.
- High-dimensional spaces encode more features, which can preserve nuance, but they also increase storage, latency, and compute.
- Embedding quality is not just “more dimensions is better”; the useful tradeoff is representational richness versus operational cost.
- Manual calculation is valuable because it exposes what the model is really measuring: angle, not absolute distance.

## Implementation Overview

- This lab uses the OpenAI embeddings API to embed two sentences, then computes cosine similarity manually in Python.
- The script also records the dot product, vector magnitudes, and embedding metadata such as model and dimension.
- A small JSON file, `embeddings.json`, stores the embeddings and the derived similarity metrics.

## How It Works

1. Load environment variables with `python-dotenv` and initialize the OpenAI client.
2. Load `embeddings.json` if it exists; otherwise create an empty file.
3. Create two embeddings from the sample sentences.
4. Validate that both vectors have the same length.
5. Compute dot product, vector magnitudes, and cosine similarity manually.
6. Print the results and classify the pair as similar or not similar.
7. Append both embeddings and the derived metrics back into `embeddings.json`.

## Example Usage

```bash
python main.py
```

Example sentence pair from the script:

```python
Embedding(["The dog ran really fast after the car."], "text-embedding-3-small").create()
Embedding(["The dog ran fast by the car."], "text-embedding-3-small").create()
```

## Next Steps

- Compare `text-embedding-3-small` against `text-embedding-3-large` to observe the dimensionality tradeoff.
- Add a reusable helper for comparing arbitrary sentence pairs.
- Store the raw input text and similarity output in a more structured JSON schema.
- Add a small threshold experiment to see how cosine similarity changes across different sentence pairs.
