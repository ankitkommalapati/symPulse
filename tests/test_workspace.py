"""Static delivery must coexist with evidence routes without a catch-all."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pulse.api import create_app
from pulse.config import Settings


class WorkspaceDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings.load({}, self.root)

    def client(self):
        with patch('pulse.api.ROOT', self.root):
            client = TestClient(create_app(self.settings))
        self.addCleanup(client.close)
        return client

    def test_unbuilt_workspace_has_clear_failure_but_api_is_live(self):
        client = self.client()
        self.assertEqual(client.get('/').status_code, 503)
        self.assertEqual(client.get('/health/live').status_code, 200)
        self.assertEqual(client.get('/api/unknown').status_code, 404)

    def test_static_assets_do_not_shadow_api_or_expose_project_files(self):
        dist = self.root / 'apps/web/dist'
        (dist / 'assets').mkdir(parents=True)
        (dist / 'index.html').write_text('<html><title>symPulse</title></html>')
        (dist / 'pulse.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        (dist / 'assets/app.js').write_text('console.log("Pulse")')
        (dist / 'secret.txt').write_text('private')
        client = self.client()
        index = client.get('/')
        self.assertEqual(index.status_code, 200)
        self.assertEqual(index.headers['cache-control'], 'no-cache')
        self.assertIn('text/html', index.headers['content-type'])
        self.assertEqual(client.get('/assets/app.js').status_code, 200)
        self.assertIn('image/svg+xml', client.get('/pulse.svg').headers['content-type'])
        self.assertEqual(client.get('/api/meta').json()['application'], 'symPulse')
        for path in ('/assets/unknown.js', '/assets/%2e%2e/secret.txt', '/secret.txt', '/api/unknown', '/investigation/ICU'):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 404)
