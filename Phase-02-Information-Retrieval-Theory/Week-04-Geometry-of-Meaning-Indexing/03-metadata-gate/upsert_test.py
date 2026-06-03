import os
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

pinecone_client = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("INDEX_NAME")

sample = [{
  "id": "test-0001",
  "chunk_text": "Test billing issue: I was charged incorrectly.",
  "ticket_type": "Billing inquiry",
  "ticket_priority": "critical",
  "date_ts": 1710000000
}]

index_info = pinecone_client.describe_index(index_name)
pinecone_index = pinecone_client.Index(host=index_info.host)

response = pinecone_index.upsert_records(namespace="default", records=sample)
print("Upsert response:", response)