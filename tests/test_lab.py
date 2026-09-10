import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('lab', Path(__file__).resolve().parents[1] / 'tooling/lab.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)

AUTH = ['--authorized-by', 'owner@example', '--auth-method', 'written scope confirmation']
LOCAL = ['--allow-insecure', '--allow-private']  # the test server is http on loopback


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', 'http://unapproved.invalid/')
            self.end_headers()
        else:
            self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *args): pass


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = lab.ROOT
        lab.ROOT = Path(self.temp.name)
        self.p = lab.ROOT / 'products/demo'
        (self.p / 'runs').mkdir(parents=True)
        lab.save(self.p / 'product.json', {'schema_version': 1, 'name': 'Demo', 'slug': 'demo', 'priority': 'test', 'environments': {e: {'url': '', 'enabled': False, 'allowed_hosts': [], 'approved_actions': ['read-only'], 'build': 'unknown'} for e in ('staging', 'production')}})
        lab.save(self.p / 'cases/catalog.json', [{'id': 'WEB-001', 'mandatory': True}, {'id': 'PRODUCT-001', 'mandatory': True}])
        (lab.ROOT / 'templates').mkdir()
        (lab.ROOT / 'templates/peer-review.md').write_text('Pending review')
        (lab.ROOT / 'standards').mkdir()
        (lab.ROOT / 'standards/testing-standard.md').write_text('baseline standard')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        lab.ROOT = self.original; self.temp.cleanup()

    def call(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return lab.main(list(args))

    def configure(self, path='', env='staging', extra=()):
        return self.call('configure', 'demo', '--env', env, '--url', self.url + path, *AUTH, *LOCAL, *extra)

    def start(self, path=''):
        self.configure(path)
        self.call('new-run', 'demo', '--env', 'staging', '--agent', 'codex')
        return sorted((self.p / 'runs').iterdir())[-1]

    def test_unset_url_blocks_run(self):
        with self.assertRaises(ValueError): self.call('new-run', 'demo', '--env', 'staging', '--agent', 'codex')
        self.assertEqual(list((self.p / 'runs').iterdir()), [])

    def test_smoke_and_report_do_not_imply_readiness(self):
        r = self.start()
        self.assertEqual(self.call('smoke', 'demo', '--run', r.name, '--agent', 'codex'), 0)
        self.call('report', 'demo', '--run', r.name)
        text = (r / 'report.md').read_text()
        self.assertIn('WEB-001 | passed', text); self.assertIn('PRODUCT-001 | not-run', text)
        self.assertIn('NOT ESTABLISHED', text); self.assertIn('Authorization:', text)

    def test_external_redirect_blocked(self):
        r = self.start('/redirect')
        self.assertEqual(self.call('smoke', 'demo', '--run', r.name, '--agent', 'codex'), 2)
        result = lab.read(next((r / 'results/codex').glob('*.json')))
        self.assertEqual(result['status'], 'blocked')

    def test_scope_snapshot_does_not_change(self):
        r = self.start()
        self.configure('/changed')
        self.assertEqual(lab.read(r / 'manifest.json')['scope']['url'], self.url)

    def test_ownership_and_duplicate_claim(self):
        r = self.start()
        with self.assertRaises(ValueError): self.call('smoke', 'demo', '--run', r.name, '--agent', 'claude')
        with self.assertRaises(ValueError): self.call('claim', 'demo', '--run', r.name, '--agent', 'codex')
        self.call('release', 'demo', '--run', r.name, '--agent', 'codex')
        with self.assertRaises(ValueError): self.call('smoke', 'demo', '--run', r.name, '--agent', 'codex')
        self.call('claim', 'demo', '--run', r.name, '--agent', 'codex')

    def test_result_requires_evidence_and_prevents_path_escape(self):
        r = self.start()
        with self.assertRaises(ValueError): lab.record(r, 'codex', 'WEB-001', 'passed', 'ok', [])
        with self.assertRaises(ValueError): lab.record(r, 'codex', 'WEB-001', 'passed', 'ok', ['../../product.json'])
        with self.assertRaises(ValueError): lab.record(r, 'codex', 'FAKE', 'blocked', 'unknown', [])

    def test_closed_run_rejects_mutation(self):
        r = self.start()
        self.call('close', 'demo', '--run', r.name, '--agent', 'codex')
        before = (r / 'report.md').read_text()
        with self.assertRaises(ValueError): self.call('report', 'demo', '--run', r.name)
        with self.assertRaises(ValueError): self.call('claim', 'demo', '--run', r.name, '--agent', 'codex')
        self.assertEqual(before, (r / 'report.md').read_text())

    def test_config_rejects_secret_urls(self):
        for url in ('https://user:secret@example.com', 'https://example.com/?token=secret'):
            with self.assertRaises(ValueError):
                self.call('configure', 'demo', '--env', 'production', '--url', url, *AUTH)

    def test_configure_requires_authorization(self):
        with self.assertRaises(SystemExit):
            self.call('configure', 'demo', '--env', 'staging', '--url', self.url, *LOCAL)

    def test_plain_http_needs_allow_insecure(self):
        with self.assertRaises(ValueError):
            self.call('configure', 'demo', '--env', 'staging', '--url', self.url, *AUTH, '--allow-private')
        self.assertEqual(self.configure(), 0)

    def test_loopback_needs_allow_private(self):
        with self.assertRaises(ValueError):
            self.call('configure', 'demo', '--env', 'staging', '--url', self.url, *AUTH, '--allow-insecure')

    def test_cloud_metadata_always_blocked(self):
        with self.assertRaises(ValueError):
            self.call('configure', 'demo', '--env', 'staging', '--url', 'https://169.254.169.254/latest/meta-data',
                      *AUTH, '--allow-private', '--allow-insecure')

    def test_expired_scope_blocks_new_run(self):
        self.configure()
        c = lab.read(self.p / 'product.json')
        c['environments']['staging']['expires_at'] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        lab.save(self.p / 'product.json', c)
        with self.assertRaises(ValueError): self.call('new-run', 'demo', '--env', 'staging', '--agent', 'codex')

    def test_disable_clears_scope(self):
        self.configure()
        self.assertEqual(self.call('disable', 'demo', '--env', 'staging'), 0)
        env = lab.read(self.p / 'product.json')['environments']['staging']
        self.assertFalse(env['enabled']); self.assertEqual(env['url'], '')
        with self.assertRaises(ValueError): self.call('new-run', 'demo', '--env', 'staging', '--agent', 'codex')

    def test_redaction_guard_blocks_secret_and_identity(self):
        r = self.start()
        with self.assertRaises(ValueError):
            lab.record(r, 'codex', 'WEB-001', 'blocked', 'auth header was Bearer abcdef0123456789xyz', [])
        lab.save(lab.ROOT / 'local/identity.json', {'gmail_address': 'qaexample@gmail.com', 'phone_number': '+15555550100'})
        with self.assertRaises(ValueError):
            lab.record(r, 'codex', 'WEB-001', 'blocked', 'signed in as qaexample@gmail.com', [])

    def test_verify_sources_detects_drift(self):
        r = self.start()
        self.assertEqual(self.call('verify-sources', 'demo', '--run', r.name), 0)
        (lab.ROOT / 'standards/testing-standard.md').write_text('changed after run creation')
        self.assertEqual(self.call('verify-sources', 'demo', '--run', r.name), 2)

    def test_runs_listing(self):
        r = self.start()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            lab.main(['runs', 'demo'])
        self.assertIn(r.name, out.getvalue())

    def test_aliases_are_private_and_do_not_create_accounts(self):
        r = self.start()
        lab.save(lab.ROOT / 'local/identity.json', {'gmail_address': 'qaexample@gmail.com'})
        lab.save(self.p / 'fixtures/personas.json', {'personas': ['doctor-a', 'care-seeker-a']})
        self.call('aliases', 'demo', '--run', r.name, '--agent', 'codex')
        data = lab.read(r / 'private/aliases.json')
        self.assertEqual(len(data['aliases']), 2)
        self.assertTrue(all(not a['created'] for a in data['aliases']))
        self.assertNotIn('qaexample', (r / 'report.md').read_text())


if __name__ == '__main__':
    unittest.main()
