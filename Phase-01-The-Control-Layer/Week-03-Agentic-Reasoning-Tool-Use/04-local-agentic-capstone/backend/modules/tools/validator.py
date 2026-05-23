"""Validate tool invocation args against a manifest-defined schema."""
from __future__ import annotations

import json
from typing import Any, Dict

from jsonschema import Draft7Validator, ValidationError as JSONSchemaValidationError

from .manifest_schema import TOOL_MANIFEST_SCHEMA


class ManifestValidationError(Exception):
    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__("manifest validation failed")
        self.errors = errors


def validate_manifest(manifest: Dict[str, Any]) -> None:
    v = Draft7Validator(TOOL_MANIFEST_SCHEMA)
    errors = list(v.iter_errors(manifest))
    if errors:
        raise ManifestValidationError([{"message": e.message, "path": list(e.path)} for e in errors])


def validate_args(manifest: Dict[str, Any], args: Dict[str, Any]) -> None:
    """Validate an args dict against the manifest's `inputs` JSON Schema.

    The manifest must include a full JSON Schema in `manifest['inputs']` with `type: object`.
    """
    validate_manifest(manifest)
    input_schema = manifest["inputs"]
    try:
        v = Draft7Validator(input_schema)
        errors = list(v.iter_errors(args))
        if errors:
            raise ManifestValidationError([
                {"message": e.message, "path": list(e.path)} for e in errors
            ])
    except JSONSchemaValidationError as e:
        raise ManifestValidationError([{"message": str(e), "path": []}])
