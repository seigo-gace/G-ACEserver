import sys
from pathlib import Path
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from chat_host_offline import inspect_once
from chat_host_ledger import RequestLedger, ReplayDenied
from chat_host_admission import AdmissionDenied

SHA="a"*40
NOW=datetime(2026,10,31,12,0,tzinfo=timezone.utc)
def request():
    return {"request_id":"req_123456789abc", "project":"Gserver",
            "change_unit":"GSR-CHAT-HOST-01", "repository":"seigo-gace/G-ACEserver",
            "source_sha":SHA,"command_id":"project.git_head","effect":"read_only",
            "issued_at":NOW.isoformat()}

class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.ledger=RequestLedger(self.root/"claims.sqlite")
    def inspect(self, r):
        return inspect_once(r,change_unit="GSR-CHAT-HOST-01",source_sha=SHA,
                            now=NOW,registered_checkout=self.root,ledger=self.ledger)
    @patch("chat_host_offline.observe_owned_checkout",return_value={"head_matches":True})
    def test_one_and_duplicate(self, git):
        self.assertTrue(self.inspect(request())["result"]["head_matches"])
        with self.assertRaises(ReplayDenied): self.inspect(request())
        self.assertEqual(git.call_count,1)
    @patch("chat_host_offline.observe_owned_checkout",side_effect=AdmissionDenied("LOCAL_GIT_FAILED"))
    def test_failed_consumes_id(self, git):
        with self.assertRaises(AdmissionDenied): self.inspect(request())
        with self.assertRaises(ReplayDenied): self.inspect(request())
        self.assertEqual(git.call_count,1)
    @patch("chat_host_offline.observe_owned_checkout")
    def test_unadmitted_never_calls_git(self, git):
        r=request();r["effect"]="write"
        with self.assertRaises(AdmissionDenied): self.inspect(r)
        git.assert_not_called()
    @patch("chat_host_offline.observe_owned_checkout")
    def test_reboot_duplicate(self, git):
        git.return_value={"head_matches":True}
        self.inspect(request())
        self.ledger=RequestLedger(self.root/"claims.sqlite")
        with self.assertRaises(ReplayDenied): self.inspect(request())
        self.assertEqual(git.call_count,1)
