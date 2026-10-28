"""Guard owner-only Gserver Bot deployment acceptance against surprise actions."""
from pathlib import Path
import ast
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gserver_bot_ready.py"


class BotReadyDeploymentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = SCRIPT.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.content, filename=str(SCRIPT))

    def test_build_requires_explicit_install(self):
        self.assertIn('parser.add_argument("--install", action="store_true"', self.content)
        self.assertIn("if args.install:", self.content)
        self.assertIn("run_tests()", self.content)

    def test_docker_space_and_immutable_activation_gates(self):
        self.assertIn("MIN_AVAILABLE_BYTES = 2 * 1024 ** 3", self.content)
        self.assertIn("control.activate(image)", self.content)
        self.assertIn('image.startswith("sha256:")', self.content)
        self.assertIn('"--pull=false"', self.content)

    def test_existing_bot_and_ports_not_overridden(self):
        self.assertIn('control.action("enable-local")', self.content)
        self.assertIn('control.action("bot-init")', self.content)
        self.assertIn('control.action("bot-smoke")', self.content)
        self.assertNotIn('"8765:8765"', self.content)
        self.assertNotIn("docker system prune", self.content)
        self.assertNotIn("volume rm", self.content)

    def test_no_fake_tgserver_delivery_proof(self):
        self.assertIn("BOT_GATEWAY_REMOTE=NOT_VERIFIED", self.content)
        self.assertIn("TGSERVER_TELEGRAM_RAW_SEARCH=NOT_VERIFIED", self.content)
        self.assertIn("BOT_GSERVER_LOCAL=PASS", self.content)


if __name__ == "__main__":
    unittest.main()
