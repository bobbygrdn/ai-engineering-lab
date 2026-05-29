from openai import OpenAI
import json
from dotenv import load_dotenv
import os
import math

load_dotenv()
client = OpenAI()
client.api_key = os.getenv("OPENAI_API_KEY")

try:
    with open("embeddings.json", "r") as f:
        json_list = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    json_list = []
    with open("embeddings.json", "w") as f:
        json.dump(json_list, f, indent=4)

class Embedding:
    def __init__(self, input: list[str], model: str):
        self.input = input
        self.model = model

    def create(self):
        if self.model not in ["text-embedding-3-small", "text-embedding-3-large"]:
            print("Invalid model specified. Defaulting to 'text-embedding-3-small'.")
            self.model = "text-embedding-3-small"

        response = client.embeddings.create(input=self.input, model=self.model)
        large_embedding = 3072
        small_embedding = 1536

        if self.model == "text-embedding-3-small":
            dimension = small_embedding
        elif self.model == "text-embedding-3-large":
            dimension = large_embedding

        return {
            "input": self.input,
            "embedding": response.data[0].embedding,
            "dimension": dimension
        }

embedding1 = Embedding(["The dog ran really fast after the car."], "text-embedding-3-small").create()
embedding2 = Embedding(["The dog ran fast by the car."], "text-embedding-3-small").create()

check_length_match = len(embedding1["embedding"]) == len(embedding2["embedding"])

if not check_length_match:
    print("Error: The embeddings have different dimensions.")
    exit(1)

def dot_product(vec1, vec2):
    return sum(a * b for a, b in zip(vec1, vec2))


def magnitude(vec):
    return math.sqrt(sum(a ** 2 for a in vec))

def cosine_similarity(vec1, vec2):
    dot_prod = dot_product(vec1, vec2)
    magnitude1 = magnitude(vec1)
    magnitude2 = magnitude(vec2)

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0  # Avoid division by zero

    return {
        "cosine_similarity": dot_prod / (magnitude1 * magnitude2),
        "dot_product": dot_prod,
        "magnitude1": magnitude1,
        "magnitude2": magnitude2
    }

cosine_sim = cosine_similarity(embedding1["embedding"], embedding2["embedding"])
print(f"Cosine similarity: {cosine_sim['cosine_similarity']}")
print(f"Dot product: {cosine_sim['dot_product']}")
print(f"Magnitude 1: {cosine_sim['magnitude1']}")
print(f"Magnitude 2: {cosine_sim['magnitude2']}")

if cosine_sim['cosine_similarity'] > 0.8:
    print("The sentences are similar.")
else:
    print("The sentences are not similar.")


json_list.append(embedding1)
json_list.append(embedding2)
json_list.append({
    "cosine_similarity": cosine_sim["cosine_similarity"],
    "dot_product": cosine_sim["dot_product"],
    "magnitude1": cosine_sim["magnitude1"],
    "magnitude2": cosine_sim["magnitude2"]
})

with open("embeddings.json", "w") as f:
    json.dump(json_list, f, indent=4)