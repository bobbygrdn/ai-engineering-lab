from main import process_email
from logger import logging
from tabulate import tabulate

def log_benchmark_result(email, valid, cost):
    logging.info(f"Email: {email[:50]}... | Valid: {valid} | Cost: ${cost:.4f}")

def print_summary_table(result):
    table = [
        [i+1, r["email"][:40] + "...", r["valid"], f"${r['cost']:.4f}"]
        for i, r in enumerate(result)
    ]
    print(tabulate(table, headers=["#", "Email", "Valid", "Cost"]))

def run_benchmark():
    test_emails = [
        "Hello, I was charged twice for my subscription and I need a refund. Please help me resolve this issue as soon as possible.",
        "My internet connection is very slow and keeps dropping. Can you please fix this?",
        "I want to change my billing address, but I can't find the option in my account settings.",
        "The app crashes every time I try to upload a photo. Please help!",
        "I have a question about my recent invoice. Can you explain the charges?",
        "",
        "The product I received is defective. I want a replacement or a refund.",
        "I want to cancel my subscription, but I can't find the cancellation option.",
        "I have a suggestion for a new feature. Who can I talk to about this?",
        "I accidentally deleted my account. Can you help me recover it?",
        "I have been waiting for a response for over a week. Why is my ticket still open?",
        "I need help with integrating your API into my application. Can you provide documentation?",
        "I want to upgrade my plan, but I'm not sure which one is right for me. Can you help?",
        "I have a security concern about my account. Who can I contact to discuss this?",
        "I want to provide feedback on your customer service. Who can I talk to about this?",
        "I need help with a technical issue that is affecting my business. Can you provide priority support?",
        "",
        "I want to report a bug that I found in your software. Who can I contact about this?",
        "I need help with a billing issue that is preventing me from using your service. Can you assist me?",
        "I want to request a feature that would make your product more useful for my needs. Who can I talk to about this?"
    ]
    result = []
    for email in test_emails:
        response, metadata = process_email(email)
        valid = response is not None
        cost = metadata.get("cost", 0) if metadata else 0
        result.append({
            "email": email,
            "valid": valid,
            "cost": cost
        })
        log_benchmark_result(email, valid, cost)

    accuracy = sum(r["valid"] for r in result) / len(result)
    avg_cost = sum(r["cost"] for r in result) / max(1, sum(r["valid"] for r in result))

    print(f"Accuracy vs. Schema: {accuracy:.2%}")
    print(f"Average Cost per Ticket: ${avg_cost:.4f}")
    print_summary_table(result)
    return result

if __name__ == "__main__":
    run_benchmark()