import csv
import os
import time
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

CSV_PATH = Path("data/clean/customer_support_tickets.csv")
BATCH_SIZE = 96
INDEX_NAME = os.getenv("INDEX_NAME")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
NAMESPACE = os.getenv("NAMESPACE", "default")

pinecone_client = Pinecone(api_key=PINECONE_API_KEY)

def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            yield r

def parse_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return value

def parse_int(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None

def normalize_scalar(value):
    value = parse_bool(value)
    if isinstance(value, str):
        int_value = parse_int(value)
        if int_value is not None:
            return int_value
    return value

def to_record(row: Dict) -> Dict:
    record = {
        "id": normalize_scalar(row["id"]),
        "chunk_text": row.get("chunk_text", ""),
        "ticket_subject": row.get("ticket_subject", ""),
        "ticket_type": row.get("ticket_type", ""),
        "ticket_priority": row.get("ticket_priority", ""),
        "ticket_channel": row.get("ticket_channel", ""),
        "ticket_status": row.get("ticket_status", ""),
        "product_purchased": row.get("product_purchased", ""),
        "date_ts": parse_int(row.get("date_ts")),
        "customer_satisfaction_rating": parse_int(row.get("customer_satisfaction_rating")),
        "age_band": row.get("age_band", ""),
        "issue_family": row.get("issue_family", ""),
        "issue_severity": row.get("issue_severity", ""),
        "needs_immediate_attention": parse_bool(row.get("needs_immediate_attention")),
    }

    return {key: value for key, value in record.items() if value is not None and value != ""}

def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"Clean CSV not found: {CSV_PATH}")

    if not INDEX_NAME:
        raise SystemExit("INDEX_NAME not set in environment")

    index_info = pinecone_client.describe_index(INDEX_NAME)
    pinecone_index = pinecone_client.Index(host=index_info.host)

    batch = []
    total = 0

    for row in read_rows(CSV_PATH):
        batch.append(to_record(row))
        total += 1

        if len(batch) >= BATCH_SIZE:
            response = pinecone_index.upsert_records(namespace=NAMESPACE, records=batch)
            print(f"Upserted {len(batch)} records, total so far {total}")
            print(response)
            batch = []
            time.sleep(0.1)

    if batch:
        response = pinecone_index.upsert_records(namespace=NAMESPACE, records=batch)
        print(f"Upserted final {len(batch)} records, total {total}")
        print(response)

    print("Done.")

if __name__ == "__main__":
    main()