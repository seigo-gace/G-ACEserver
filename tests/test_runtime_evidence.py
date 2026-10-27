import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('evidence', Path(__file__).resolve().parents[1] / 'scripts/runtime_evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class EvidenceTests(unittest.TestCase):
    def test_receipt_separates_runtime_scope_and_final_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            evidence.save(Path(d), 'a'*40, 'a'*40, 'PACKAGED_RUNTIME', 0)
            data = json.loads((Path(d) / 'latest.json').read_text())
            self.assertEqual(data['status'], 'PASS')
            self.assertEqual(data['f01_f08'], 'NOT_COMPLETE')

    def test_source_change_cannot_be_pass(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(evidence.save(Path(d), 'a'*40, 'b'*40, 'SOURCE_CHANGED', 0)['status'], 'FAIL')

    def test_failure_preserved_and_arbitrary_details_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(evidence.save(Path(d), 'a'*40, 'a'*40, 'EXISTING_SOURCE_STAGING', 16)['exit_code'], 16)
            with self.assertRaises(ValueError):
                evidence.save(Path(d), 'a'*40, 'a'*40, 'password=private', 0)
