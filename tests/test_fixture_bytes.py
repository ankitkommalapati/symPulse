"""Source extracts retain the exact bytes recorded in their manifest."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.generate_data import generate
from scripts.validate_data import validate


class FixtureByteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        original = Path.write_text

        def translated_write(path, text, *args, **kwargs):
            return original(path, text.replace('\n', '\r\n'), *args, **kwargs)

        # Exercise a host that translates text-mode newlines without changing
        # the manifest's hashing or the validator's strict byte comparison.
        with patch.object(Path, 'write_text', translated_write), contextlib.redirect_stdout(io.StringIO()):
            generate(42, cls.folder)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_manifest_matches_canonical_source_bytes_after_text_translation(self):
        manifest = json.loads((self.folder / 'manifest.json').read_text())
        for table, metadata in manifest['tables'].items():
            with self.subTest(table=table):
                raw = (self.folder / (table + '.jsonl')).read_bytes()
                self.assertFalse(b'\r\n' in raw, 'JSONL must retain LF bytes')
                self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata['sha256'])
                self.assertEqual(len(raw.splitlines()), metadata['records'])
        with contextlib.redirect_stdout(io.StringIO()):
            validate(self.folder)

    def test_validator_still_rejects_changed_source_bytes(self):
        path = self.folder / 'access_policy_requirements.jsonl'
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(b'\n', b'\r\n'))
            with self.assertRaisesRegex(AssertionError, 'access_policy_requirements manifest hash'):
                validate(self.folder)
        finally:
            path.write_bytes(original)
