import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import query_with_filters as q


def test_parse_date_arg_epoch():
    assert q.parse_date_arg("1710000000") == 1710000000


def test_parse_date_arg_iso_date():
    assert q.parse_date_arg("2024-03-01") == 1709251200


def test_merge_date_range_into_filter():
    base = {"ticket_type": {"$eq": "Billing inquiry"}}
    merged = q.merge_date_range_into_filter(base, 1700000000, 1710000000)
    assert merged["ticket_type"] == {"$eq": "Billing inquiry"}
    assert merged["date_ts"] == {"$gte": 1700000000, "$lte": 1710000000}


def test_normalize_metadata_values_converts_booleans_and_date():
    data = {
        "needs_immediate_attention": "false",
        "date_ts": "2024-03-01",
        "ticket_priority": "High",
    }
    out = q._normalize_metadata_values(data)
    assert out["needs_immediate_attention"] is False
    assert out["date_ts"] == 1709251200
    assert out["ticket_priority"] == "High"


def test_extract_hits_from_search_response_object():
    resp = SimpleNamespace(result=SimpleNamespace(hits=[{"id": "1"}]))
    hits = q._extract_hits(resp)
    assert hits == [{"id": "1"}]


def test_normalize_match_prefers_fields_and_metadata():
    match = {
        "id": "2033",
        "score": 0.5,
        "metadata": {
            "needs_immediate_attention": "true",
            "date_ts": "1710000000",
        },
    }
    out = q._normalize_match(match)
    assert out["id"] == "2033"
    assert out["fields"]["needs_immediate_attention"] is True
    assert out["fields"]["date_ts"] == 1710000000


def test_query_index_writes_csv(monkeypatch, tmp_path):
    fake_resp = {
        "result": {
            "hits": [
                {
                    "id": "2033",
                    "score": 0.49,
                    "metadata": {
                        "ticket_type": "Billing inquiry",
                        "ticket_priority": "High",
                        "chunk_text": "Wrong amount billed",
                        "date_ts": 1710000000,
                    },
                }
            ]
        }
    }

    class FakeIndex:
        def search(self, **kwargs):
            return fake_resp

    monkeypatch.setattr(q, "index", FakeIndex())

    csv_path = tmp_path / "results.csv"
    matches = q.query_index(
        "wrong amount billed",
        filter_obj={"ticket_type": {"$eq": "Billing inquiry"}},
        top_k=3,
        namespace=None,
        fields=["ticket_type", "ticket_priority", "chunk_text", "date_ts"],
        dump_csv_path=str(csv_path),
    )

    assert len(matches) == 1
    assert csv_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1
    assert rows[0]["id"] == "2033"
    assert rows[0]["ticket_type"] == "Billing inquiry"
    assert rows[0]["ticket_priority"] == "High"


def test_query_index_none_namespace_omits_namespace(monkeypatch):
    captured = {}

    class FakeIndex:
        def search(self, **kwargs):
            captured.update(kwargs)
            return {"result": {"hits": []}}

    monkeypatch.setattr(q, "index", FakeIndex())

    q.query_index("wrong amount billed", namespace=None, fields=["ticket_type"])
    assert "namespace" not in captured


def test_query_index_default_namespace_string(monkeypatch):
    captured = {}

    class FakeIndex:
        def search(self, **kwargs):
            captured.update(kwargs)
            return {"result": {"hits": []}}

    monkeypatch.setattr(q, "index", FakeIndex())

    q.query_index("wrong amount billed", namespace="default", fields=["ticket_type"])
    assert captured["namespace"] == "default"