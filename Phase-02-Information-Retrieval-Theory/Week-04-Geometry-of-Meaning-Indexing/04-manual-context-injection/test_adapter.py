import adapter

def test_build_context_prompt_uses_doc_and_chunk_fields(monkeypatch):
    def fake_query_index(*args, **kwargs):
        return [
            {
                "id": "ticket-9-1",
                "score": 0.91,
                "fields": {
                    "doc_id": "ticket-9",
                    "chunk_id": 1,
                    "chunk_text": "Billing got billed twice for the same month.",
                },
            }
        ]

    monkeypatch.setattr(adapter, "query_index", fake_query_index)

    result = adapter.build_context_prompt("Why was this billed twice?")

    assert result["matches"][0]["fields"]["doc_id"] == "ticket-9"
    assert result["selected"][0]["doc_id"] == "ticket-9"
    assert result["selected"][0]["chunk_ids"] == [1]
    assert "Billing got billed twice" in result["system_prompt"]
