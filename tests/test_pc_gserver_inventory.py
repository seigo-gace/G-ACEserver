"""Run with: python3 -m unittest discover -s tests -v"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "pc_gserver_inventory.py"
spec = importlib.util.spec_from_file_location("pc_gserver_inventory", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PcGserverInventoryTest(unittest.TestCase):
    def test_missing_path_remains_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            result = mod.inventory_root("sample", Path(temp) / "missing")
            self.assertEqual(result["status"], "MISSING_OR_NOT_DIRECTORY")

    def test_scans_source_and_marks_hints_without_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "main.py").write_text('print("https://api.github.com/repos")\n', encoding="utf-8")
            (root / ".env").write_text("GITHUB_TOKEN=secret", encoding="utf-8")
            (root / "secrets.py").write_text("password='oops'", encoding="utf-8")
            out = mod.inventory_root("sample", root)
            self.assertEqual(out["status"], "READ_ONLY_SCANNED")
            self.assertEqual([f["relative"] for f in out["files"]], ["main.py"])
            self.assertIn("github_api", {h["category"] for h in out["files"][0]["review_hints"]})
            self.assertNotIn("secret", str(out))

    def test_root_symlink_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            self.assertEqual(mod.inventory_root("sample", root / "link")["status"], "SYMLINK_ROOT_SKIPPED")

    def test_bounded_name_discovery_finds_only_gserver(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sub" / "GSERVER").mkdir(parents=True)
            (root / "other").mkdir()
            found = mod.discover_named_roots({"mock": root})
            self.assertEqual(len(found), 1)
            self.assertEqual(next(iter(found.values())).name, "GSERVER")

    def test_bounds_large_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "big.py").write_bytes(b"x" * (mod.MAX_BYTES + 1))
            out = mod.inventory_root("sample", root)
            self.assertEqual(out["skipped"], 1)
            self.assertEqual(out["files"], [])


if __name__ == "__main__":
    unittest.main()
