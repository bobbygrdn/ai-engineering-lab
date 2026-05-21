from modules.memory.recursive_compressor import recursive_compress
from modules.memory.working_memory import MessageObject, StoredMessage


def test_recursive_compress_reduces_tokens_and_keeps_recent_context():
    messages = [
        StoredMessage(message=MessageObject(role="system", content="system instructions"), token_count=5),
    ]

    for i in range(6):
        messages.append(
            StoredMessage(
                message=MessageObject(role="user", content=f"short message {i}"),
                token_count=200,
            )
        )

    original_total = sum(message.token_count for message in messages)

    compressed_messages, compressed_total = recursive_compress(messages, token_budget=100)

    assert compressed_total < original_total
    assert compressed_messages[-1].message.content == "short message 5"
    assert any(
        message.message.role == "assistant" and message.message.content.startswith("Summary of earlier conversation:")
        for message in compressed_messages
    )
