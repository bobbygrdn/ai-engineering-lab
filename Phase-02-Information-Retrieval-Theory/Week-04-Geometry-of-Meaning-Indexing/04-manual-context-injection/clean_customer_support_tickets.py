from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

RAW_PATH = Path("data/raw/customer_support_tickets.csv")
CLEAN_PATH = Path("data/clean/customer_support_tickets.csv")
QUARANTINE_PATH = Path("data/quarantine/customer_support_tickets.csv")

ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}
ALLOWED_CHANNELS = {"email", "web", "phone", "chat", "social media"}
ALLOWED_STATUS = {"open", "closed", "pending customer response"}
TYPE_MAP = {
    "billing inquiry": "billing",
    "refund request": "refund",
    "cancellation request": "cancellation",
    "technical issue": "technical",
    "product inquiry": "product"
}

def normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value

def slugify(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("_")

def parse_date_to_ts(value: str) -> Optional[int]:
    value = normalize_text(value)
    if not value:
        return None

    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None

def age_band(age_value: str) -> str:
    try:
        age = int(float(age_value))
    except (TypeError, ValueError):
        return "unknown"

    if age < 25:
        return "18-24"
    if age< 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 55:
        return "45-54"
    if age < 65:
        return "55-64"
    return "65+"

def issue_family(ticket_type: str, subject: str) -> str:
    ticket_type_norm = normalize_text(ticket_type).lower()
    subject_norm = normalize_text(subject).lower()

    if ticket_type_norm in TYPE_MAP:
        return TYPE_MAP[ticket_type_norm]

    if "billing" in subject_norm or "invoice" in subject_norm or "charge" in subject_norm:
        return "billing"
    if "refund" in subject_norm or "return" in subject_norm:
        return "refund"
    if "cancel" in subject_norm:
        return "cancellation"
    if "error" in subject_norm or "bug" in subject_norm or "issue" in subject_norm or "problem" in subject_norm:
        return "technical"
    if "purchase" in subject_norm or "comparison" in subject_norm or "compatibility" in subject_norm:
        return "product"

    return "other"

def severity(priority: str) -> str:
    priority_norm = normalize_text(priority).lower()
    if priority_norm in {"critical", "high"}:
        return "urgent"
    if priority_norm == "medium":
        return "normal"
    if priority_norm == "low":
        return "low"
    return "unknown"

def classify_row(row: Dict[str, str]) -> List[str]:
    errors = []

    ticket_description = normalize_text(row.get("Ticket Description", ""))
    if not ticket_description:
        errors.append("missing_ticket_description")

    date_ts = parse_date_to_ts(row.get("Date of Purchase", ""))
    if date_ts is None:
        errors.append("invalid_date")

    priority = normalize_text(row.get("Ticket Priority", "")).lower()
    if priority and priority not in ALLOWED_PRIORITIES:
        errors.append("invalid_priority")

    channel = normalize_text(row.get("Ticket Channel", "")).lower()
    if channel and channel not in ALLOWED_CHANNELS:
        errors.append("invalid_channel")

    status = normalize_text(row.get("Ticket Status", "")).lower()
    if status and status not in ALLOWED_STATUS:
        errors.append("invalid_status")

    return errors

def build_clean_row(row: Dict[str, str]) -> Dict[str, str]:
    ticket_id = normalize_text(row.get("Ticket ID", ""))
    subject = normalize_text(row.get("Ticket Subject", ""))
    description = normalize_text(row.get("Ticket Description", ""))
    ticket_type = normalize_text(row.get("Ticket Type", ""))
    priority = normalize_text(row.get("Ticket Priority", ""))
    channel = normalize_text(row.get("Ticket Channel", ""))
    status = normalize_text(row.get("Ticket Status", ""))
    product = normalize_text(row.get("Product Purchased", ""))
    satisfaction = normalize_text(row.get("Customer Satisfaction Rating", ""))
    age = normalize_text(row.get("Customer Age", ""))

    chunk_text = f"{subject}. {description}".strip(" .")

    return {
        "id": ticket_id,
        "chunk_text": chunk_text,
        "ticket_subject": subject,
        "ticket_type": ticket_type,
        "ticket_priority": priority,
        "ticket_channel": channel,
        "ticket_status": status,
        "product_purchased": product,
        "date_ts": str(parse_date_to_ts(row.get("Date of Purchase", "")) or ""),
        "customer_satisfaction_rating": satisfaction,
        "age_band": age_band(age),
        "issue_family": issue_family(ticket_type, subject),
        "issue_severity": severity(priority),
        "needs_immediate_attention": "true" if normalize_text(priority).lower() == "critical" else "false",
    }

def main() -> None:
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RAW_PATH.open("r", encoding="utf-8", newline="") as infile, \
         CLEAN_PATH.open("w", encoding="utf-8", newline="") as clean_file, \
         QUARANTINE_PATH.open("w", encoding="utf-8", newline="") as quarantine_file:

        reader = csv.DictReader(infile)

        clean_fields = [
            "id",
            "chunk_text",
            "ticket_subject",
            "ticket_type",
            "ticket_priority",
            "ticket_channel",
            "ticket_status",
            "product_purchased",
            "date_ts",
            "customer_satisfaction_rating",
            "age_band",
            "issue_family",
            "issue_severity",
            "needs_immediate_attention",
        ]
        quarantine_fields = list(reader.fieldnames or []) + ["errors"]

        clean_writer = csv.DictWriter(clean_file, fieldnames=clean_fields)
        quarantine_writer = csv.DictWriter(quarantine_file, fieldnames=quarantine_fields)

        clean_writer.writeheader()
        quarantine_writer.writeheader()

        cleaned_count = 0
        quarantined_count = 0

        for row in reader:
            errors = classify_row(row)
            if errors:
                quarantine_row = dict(row)
                quarantine_row["errors"] = "|".join(errors)
                quarantine_writer.writerow(quarantine_row)
                quarantined_count += 1
                continue

            clean_writer.writerow(build_clean_row(row))
            cleaned_count += 1

    print(f"Clean rows: {cleaned_count}")
    print(f"Quarantined rows: {quarantined_count}")
    print(f"Clean file: {CLEAN_PATH}")
    print(f"Quarantine file: {QUARANTINE_PATH}")

if __name__ == "__main__":
    main()