import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_host_ledger import RequestLedger, ReplayDenied, canonical_fingerprint

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "claims.sqlite"
        self.ledger = RequestLedger(self.path)
    def test_claim(self):
        self.assertTrue(self.ledger.claim("req_123456789abc", "a"*64))
    def test_duplicate(self):
        self.assertTrue(self.ledger.claim("req_123456789abc", "a"*64))
        self.assertFalse(self.ledger.claim("req_123456789abc", "a"*64))
    def test_restarted_duplicate(self):
        self.ledger.claim("req_123456789abc", "a"*64)
        self.assertFalse(RequestLedger(self.path).claim("req_123456789abc", "a"*64))
    def test_changed_payload_same_id(self):
        self.ledger.claim("req_123456789abc", "a"*64)
        self.assertFalse(self.ledger.claim("req_123456789abc", "b"*64))
    def test_distinct(self):
        self.assertTrue(self.ledger.claim("req_123456789abc", "a"*64))
        self.assertTrue(self.ledger.claim("req_123456789abd", "a"*64))
    def test_bad_digest(self):
        with self.assertRaises(ReplayDenied):
            self.ledger.claim("req_123456789abc", "invalid")
    def test_missing_parent(self):
        with self.assertRaises(ReplayDenied):
            RequestLedger(self.path.parent/"missing"/"db").claim("req_123456789abc", "a"*64)
    def test_fingerprint_stable(self):
        self.assertEqual(canonical_fingerprint({"a":1,"b":2}),canonical_fingerprint({"b":2,"a":1}))
    def test_fingerprint_differs(self):
        self.assertNotEqual(canonical_fingerprint({"a":1}),canonical_fingerprint({"a":2}))
