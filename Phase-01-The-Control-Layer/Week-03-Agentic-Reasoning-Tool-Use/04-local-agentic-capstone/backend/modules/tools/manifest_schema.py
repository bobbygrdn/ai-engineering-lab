"""JSON Schema helpers for tool manifests."""
from __future__ import annotations

TOOL_MANIFEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "version", "description", "inputs", "schema_version"],
    "properties": {
        "schema_version": {"type": "string"},
        "name": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "inputs": {
            "type": "object",
            # Allow schemas to include common JSON Schema keywords (properties, additionalProperties, pattern, etc.)
            "additionalProperties": True,
        },
        "allowed_callers": {"type": "array", "items": {"type": "string"}},
        "requires_framed_user_data": {"type": "boolean"},
        "allowed_roles": {"type": "array", "items": {"type": "string"}},
    },
}
