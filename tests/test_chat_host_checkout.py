import sys
from pathlib import Path
from unittest import TestCase, mock
from subprocess import CompletedProcess, TimeoutExpired
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_host_checkout import observe_owned_checkout
from chat_host_admission import AdmissionDenied
SHA = "a" * 40

class CheckoutTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
    def fake(self, args, **kwargs):
        cmd = args[-2:] if args[-2:] == ["rev-parse", "--show-toplevel"] else args[-1:]
        value = str(self.root) if cmd == ["rev-parse", "--show-toplevel"] else SHA if cmd == ["HEAD"] else ""
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["cwd"], self.root)
        return CompletedProcess(args, 0, value)
    @mock.patch("chat_host_checkout.subprocess.run")
    def test_head(self, run):
        run.side_effect = self.fake
        self.assertTrue(observe_owned_checkout(self.root, expected_sha=SHA, command_id="project.git_head")["head_matches"])
    @mock.patch("chat_host_checkout.subprocess.run")
    def test_clean(self, run):
        run.side_effect = self.fake
        self.assertTrue(observe_owned_checkout(self.root, expected_sha=SHA, command_id="project.git_status")["worktree_clean"])
    @mock.patch("chat_host_checkout.subprocess.run")
    def test_dirty(self, run):
        def f(args, **kwargs):
            if args[-1] == "--untracked-files=all":
                return CompletedProcess(args, 0, " M private-file")
            return self.fake(args, **kwargs)
        run.side_effect = f
        self.assertFalse(observe_owned_checkout(self.root, expected_sha=SHA, command_id="project.git_status")["worktree_clean"])
    @mock.patch("chat_host_checkout.subprocess.run")
    def test_sha_mismatch(self, run):
        def f(args, **kwargs):
            v = self.fake(args, **kwargs)
            if args[-1] == "HEAD":
                v.stdout = "b" * 40
            return v
        run.side_effect = f
        with self.assertRaises(AdmissionDenied):
            observe_owned_checkout(self.root, expected_sha=SHA, command_id="project.git_head")
    @mock.patch("chat_host_checkout.subprocess.run")
    def test_timeout(self, run):
        run.side_effect = TimeoutExpired("git", 5)
        with self.assertRaises(AdmissionDenied):
            observe_owned_checkout(self.root, expected_sha=SHA, command_id="project.git_head")
    def test_unknown_command(self):
        with self.assertRaises(AdmissionDenied):
            observe_owned_checkout(self.root, expected_sha=SHA, command_id="host.command")
    def test_invalid_sha(self):
        with self.assertRaises(AdmissionDenied):
            observe_owned_checkout(self.root, expected_sha="INVALID", command_id="project.git_head")
    def test_missing_checkout(self):
        with self.assertRaises(AdmissionDenied):
            observe_owned_checkout(self.root / "missing", expected_sha=SHA, command_id="project.git_head")
