"""Read-only adaptation of existing gace-dev-kb Current authority; no MVS reimplementation."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from kb_source import inspect, KBSourceError, AUTH_HASHES, CURRENT, MARKER, INTAKE


class KBSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "G-ACE-KB"
        self.root.mkdir(parents=True)
        self._write("data", "knowledge-records", "formal-kb.jsonl", value=b'{"type":"x"}\n')
        (self.root / "data" / "knowledge-search" / "records").mkdir(parents=True)
        self._write("repo", "scripts", "check-modulecatalog-kb-runtime-windows.ps1", value=b'read-only-example')

    def _write(self, *parts, value):
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        return path

    def _json(self, parts, value):
        return self._write(*parts, value=json.dumps(value, sort_keys=True).encode())

    def active(self):
        commit = "a" * 40
        hashes = {}
        for key, parts in AUTH_HASHES.items():
            if key != "formalKbSha256":
                self._write(*parts, value=(key + "\n").encode())
            hashes[key] = hashlib.sha256(self.root.joinpath(*parts).read_bytes()).hexdigest()
        data = {"status": "ACTIVE", "catalogCommit": commit,
                "projectionSchemaVersion": 2,
                "totalFormalRecordCount": 10, "knowledgeUnitCount": 8,
                "relationshipCount": 2, "caseCount": 1, **hashes}
        self._json(MARKER, data)
        self._json(CURRENT + ("runtime-state.json",), data)
        self._json(INTAKE + ("receipts", commit + ".json"), data)
        return data

    def test_absent_current_never_reports_active(self):
        result = inspect(self.root)
        self.assertEqual(result["current"], "NOT_ACTIVATED_OR_NOT_FOUND")
        self.assertFalse(result["kb_search_verified"])
        self.assertTrue(result["historical_formal_corpus_present"])

    def test_consistent_active_and_hashes_still_not_mcp(self):
        expected = self.active()
        result = inspect(self.root, verify_hashes=True)
        self.assertEqual(result["current"], "ACTIVE_AUTHORITY_HASHED")
        self.assertEqual(result["catalog_commit"], expected["catalogCommit"])
        self.assertFalse(result["kb_search_verified"])
        self.assertFalse(result["kb_mcp_deep_verified"])

    def test_hash_corruption_fail_closed(self):
        self.active()
        self._write(*AUTH_HASHES["relationshipsSha256"], value=b'tampered')
        with self.assertRaisesRegex(KBSourceError, "HASH_MISMATCH"):
            inspect(self.root, verify_hashes=True)

    def test_marker_receipt_disagreement_fails(self):
        values = self.active()
        other = dict(values, catalogCommit="b" * 40)
        self._json(CURRENT + ("runtime-state.json",), other)
        with self.assertRaisesRegex(KBSourceError, "COMMIT_MISMATCH"):
            inspect(self.root)

    def test_activation_journal_blocks_even_when_no_marker(self):
        self._write(*INTAKE, "activation-transaction.json", value=b'{}')
        with self.assertRaisesRegex(KBSourceError, "UNRESOLVED"):
            inspect(self.root)

    def test_symlinked_authority_or_file_refused(self):
        self.active()
        marker = self.root.joinpath(*MARKER)
        copy = self.root / "copy"
        copy.write_bytes(marker.read_bytes())
        marker.unlink()
        marker.symlink_to(copy)
        with self.assertRaisesRegex(KBSourceError, "SYMLINK"):
            inspect(self.root)

    def test_unsafe_count_and_broken_hash_refused(self):
        item = self.active()
        item["knowledgeUnitCount"] = -1
        self._json(MARKER, item)
        with self.assertRaisesRegex(KBSourceError, "COUNT_INVALID"):
            inspect(self.root)
        item["knowledgeUnitCount"] = 8
        item["formalKbSha256"] = "incorrect"
        self._json(MARKER, item)
        with self.assertRaisesRegex(KBSourceError, "HASH_INVALID"):
            inspect(self.root)

    def test_only_read_no_file_modification(self):
        self.active()
        marker = self.root.joinpath(*MARKER)
        before = (marker.read_bytes(), marker.stat().st_mtime_ns)
        inspect(self.root, verify_hashes=True)
        self.assertEqual((marker.read_bytes(), marker.stat().st_mtime_ns), before)


if __name__ == "__main__":
    unittest.main()
