import unittest
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_host_admission import AdmissionDenied, validate_read_only_request

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 40
CU = "GSR-CHAT-HOST-01"

def sample():
    return dict(request_id="req_123456789abc", project="Gserver", change_unit=CU,
                repository="seigo-gace/G-ACEserver", source_sha=SHA,
                command_id="project.git_head", effect="read_only", issued_at=NOW.isoformat())

class AdmissionTests(unittest.TestCase):
    def denied(self, changes):
        req = sample()
        req.update(changes)
        with self.assertRaises(AdmissionDenied):
            validate_read_only_request(req, expected_cu=CU, expected_sha=SHA, now=NOW)

    def test_allow(self):
        self.assertEqual(validate_read_only_request(sample(), expected_cu=CU, expected_sha=SHA, now=NOW)["command_id"], "project.git_head")
    def test_second_read_only(self):
        req = sample()
        req["command_id"] = "project.git_status"
        self.assertEqual(validate_read_only_request(req, expected_cu=CU, expected_sha=SHA, now=NOW)["command_id"], "project.git_status")
    def test_wrong_repo(self): self.denied({"repository": "G-ACE-inc/server-core"})
    def test_wrong_project(self): self.denied({"project": "Contabo"})
    def test_wrong_cu(self): self.denied({"change_unit": "OTHER"})
    def test_wrong_sha(self): self.denied({"source_sha": "b" * 40})
    def test_write_effect(self): self.denied({"effect": "source_write"})
    def test_shell(self): self.denied({"command_id": "host.command"})
    def test_argv(self): self.denied({"argv": ["sh", "-c", "id"]})
    def test_path(self): self.denied({"workdir": "../../"})
    def test_token(self): self.denied({"token": "secret"})
    def test_request_id(self): self.denied({"request_id": "abc"})
    def test_future(self): self.denied({"issued_at": (NOW + timedelta(seconds=1)).isoformat()})
    def test_expired(self): self.denied({"issued_at": (NOW - timedelta(seconds=61)).isoformat()})
    def test_naive(self): self.denied({"issued_at": "2026-10-31T12:00:00"})
    def test_extra_field(self): self.denied({"output": "anything"})
    def test_list_command(self): self.denied({"command_id": ["project.git_head"]})
    def test_dict_command(self): self.denied({"command_id": {"id": "project.git_head"}})
    def test_list_effect(self): self.denied({"effect": ["read_only"]})
    def test_invalid_datetime(self): self.denied({"issued_at": "not-a-date"})
    def test_invalid_now(self):
        with self.assertRaises(AdmissionDenied):
            validate_read_only_request(sample(), expected_cu=CU, expected_sha=SHA, now="now")
