import os
import json
import tempfile

from modules.tools.validator import validate_manifest, validate_args, ManifestValidationError
from modules.tools.sql_read_only import SQL_READ_ONLY_MANIFEST


def test_manifest_validates():
    # Should not raise
    validate_manifest(SQL_READ_ONLY_MANIFEST)


def test_validate_args_accepts_select():
    args = {"query": "SELECT 1 as x"}
    validate_args(SQL_READ_ONLY_MANIFEST, args)


def test_validate_args_rejects_non_select():
    args = {"query": "DROP TABLE users;"}
    try:
        validate_args(SQL_READ_ONLY_MANIFEST, args)
        assert False, "Expected ManifestValidationError"
    except ManifestValidationError as e:
        # should contain a message about pattern
        assert any("pattern" in err.get("message", "") or "SELECT" in err.get("message", "") for err in e.errors)
