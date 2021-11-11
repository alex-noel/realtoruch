"""Synthetic negative canaries for the test-only trace screen."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).with_name('sanitize_fault.py')
RUNS = ROOT / '.local/verification/T18'


class TraceScreenTests(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='screen-test-', dir=RUNS)
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name)

    def screen(self, trace, network):
        raw = self.run_dir / 'raw-fault-trace.zip'
        with ZipFile(raw, 'w') as archive:
            archive.writestr('1-trace.trace', trace)
            archive.writestr('1-trace.network', network)
            archive.writestr('resources/private.json', 'must be omitted')
            archive.writestr('screencast/page@synthetic.jpeg', b'synthetic')
        return subprocess.run([sys.executable, str(SCRIPT), str(self.run_dir)], capture_output=True)

    def test_rejects_token_and_header_canaries(self):
        token = 'SYNTHETIC-CANARY-NEVER-SHARE-0123456789'
        for label in ('verify_account', 'confirm_email', 'unsubscribe_email', 'reset_password', 'authorization', 'cookie', 'jwt'):
            with self.subTest(label=label):
                if label == 'jwt':
                    value = 'eyJ' + 'a' * 25 + '.' + 'b' * 30 + '.' + 'c' * 35
                elif label in ('verify_account', 'confirm_email', 'unsubscribe_email', 'reset_password'):
                    value = f'#{label}={token}'
                else:
                    value = token
                network = '{"headers":[{"name":"' + ('Cookie' if label == 'cookie' else 'Authorization') + '","value":"' + token + '"}]}'
                result = self.screen('{"value":"' + value + '"}', network)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.run_dir / 'sanitized-fault-trace.zip').exists())

    def test_retains_only_safe_trace_and_synthetic_screencast(self):
        result = self.screen('{"type":"action","value":"synthetic"}', '{"private":"not retained"}')
        self.assertEqual(result.returncode, 0, result.stderr)
        with ZipFile(self.run_dir / 'sanitized-fault-trace.zip') as archive:
            self.assertEqual(set(archive.namelist()), {'1-trace.trace', 'screencast/page@synthetic.jpeg'})


if __name__ == '__main__':
    unittest.main()
