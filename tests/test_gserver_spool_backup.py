from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
spec = importlib.util.spec_from_file_location('gserver_spool_backup', ROOT / 'scripts/gserver_spool_backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)

from tgs_bridge import BotSpool


def sample(event_id='backup-1'):
    return {'bot': 'profile-bot', 'event_id': event_id, 'event': 'bot.update.received',
            'level': 'info', 'outcome': 'PASS', 'error_code': 'NONE'}


class SpoolBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.spool = self.root / 'spool'
        self.archive = self.root / 'archive'
        self.output = self.root / 'restored'
        self.key = b'K' * 32
        self.queue = BotSpool(self.spool)
        self.queue.accept(sample(), now=100)
        self.queue.accept(sample('backup-2'), now=101)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_verify_restore_isolated_and_hash_checked(self):
        record = backup.create_backup(self.spool, self.archive, self.key)
        self.assertEqual(record['cipher'], 'AES-256-GCM')
        verified = backup.verify_backup(self.archive, self.key)
        self.assertTrue(verified['verified'])
        restored = backup.restore_backup(self.archive, self.output, self.key)
        self.assertTrue(restored['verified'])
        reopened = BotSpool(self.output)
        self.assertEqual(reopened.counts()['pending'], 2)
        self.assertEqual(self.queue.counts()['pending'], 2)

    def test_wrong_key_and_tampered_payload_refuse_without_restore(self):
        backup.create_backup(self.spool, self.archive, self.key)
        with self.assertRaises(backup.BackupError):
            backup.verify_backup(self.archive, b'X' * 32)
        payload = self.archive / 'payload.enc'
        data = payload.read_bytes()
        payload.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        with self.assertRaisesRegex(backup.BackupError, 'CIPHERTEXT_HASH_MISMATCH'):
            backup.verify_backup(self.archive, self.key)
        self.assertFalse(self.output.exists())

    def test_restore_never_overwrites_existing_output(self):
        backup.create_backup(self.spool, self.archive, self.key)
        self.output.mkdir()
        (self.output / 'sentinel').write_text('keep')
        with self.assertRaisesRegex(backup.BackupError, 'RESTORE_OUTPUT_MUST_BE_NEW'):
            backup.restore_backup(self.archive, self.output, self.key)
        self.assertEqual((self.output / 'sentinel').read_text(), 'keep')

    def test_key_is_not_manifest_data(self):
        backup.create_backup(self.spool, self.archive, self.key)
        manifest = json.loads((self.archive / 'manifest.json').read_text())
        self.assertNotIn(self.key.decode(), json.dumps(manifest))
        self.assertEqual((self.archive / 'manifest.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.archive / 'payload.enc').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
