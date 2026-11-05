"""Fresh demo sessions preserve saved user workflow data."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pulse.__main__ import main
from pulse.config import Settings


class DemoSessionTests(unittest.TestCase):
    def test_each_launch_uses_distinct_state_and_preserves_normal_plans(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = Settings.load({}, root)
            settings.workflow_path.parent.mkdir(parents=True)
            settings.workflow_path.write_bytes(b'existing plan state')
            dist = root / 'apps/web/dist'
            dist.mkdir(parents=True)
            (dist / 'index.html').write_text('<html>Pulse</html>')
            with patch('pulse.__main__.ROOT', root), patch('pulse.__main__.Settings.load', return_value=settings), \
                 patch('pulse.__main__.SourceRepository.check'), patch('pulse.__main__.check'), \
                 patch('pulse.api.create_app') as create, patch('uvicorn.run') as serve, \
                 patch('sys.argv', ['pulse', 'demo', '--port', '8800']), contextlib.redirect_stdout(io.StringIO()):
                main(); main()
            first, second = [call.args[0] for call in create.call_args_list]
            self.assertNotEqual(first.workflow_path, second.workflow_path)
            self.assertNotEqual(first.evidence_dir, second.evidence_dir)
            self.assertEqual(first.database_path, settings.database_path)
            self.assertEqual(settings.workflow_path.read_bytes(), b'existing plan state')
            self.assertEqual(serve.call_args.kwargs['port'], 8800)

    def test_unbuilt_demo_fails_before_starting_a_service(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch('pulse.__main__.ROOT', root), patch('pulse.__main__.Settings.load', return_value=Settings.load({}, root)), \
                 patch('uvicorn.run') as serve, patch('sys.argv', ['pulse', 'demo']), \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main()
            serve.assert_not_called()
