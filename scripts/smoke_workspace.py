#!/usr/bin/env python3
"""Verify built assets and actual HTTP-to-React flows; owns and stops its listener."""
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    npm = shutil.which('npm')
    if npm is None:
        raise RuntimeError('Node.js and npm are required; follow the workspace setup instructions')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base = 'http://127.0.0.1:' + str(port)
    env = dict(os.environ, PULSE_PORT=str(port), PULSE_HOST='127.0.0.1', VITE_PULSE_VERIFY_API=base)
    with tempfile.TemporaryDirectory(prefix='pulse-workflow-check-') as folder, tempfile.TemporaryFile(mode='w+', encoding='utf-8') as log:
        env.update(PULSE_WORKFLOW_PATH=str(Path(folder) / 'workflow.sqlite'),
                   PULSE_EVIDENCE_DIR=str(Path(folder) / 'evidence'), PULSE_LLM_ENDPOINT='',
                   PULSE_LLM_MODEL='', PULSE_LLM_API_KEY='')
        server = subprocess.Popen([sys.executable, '-m', 'pulse', 'serve'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                if server.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                try:
                    with urllib.request.urlopen(base + '/health/ready', timeout=5):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Workspace service did not become ready')
            with urllib.request.urlopen(base, timeout=5) as response:
                html = response.read().decode()
                assert 'symplr Pulse' in html
            assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
            assert assets, 'Built entry assets are missing'
            for path in assets:
                with urllib.request.urlopen(base + path, timeout=5) as response:
                    assert response.status == 200
            subprocess.run([npm, 'test', '--', 'src/live-workspace.test.tsx'], cwd=ROOT / 'apps/web', env=env, check=True)
            print('Built workspace assets and live HTTP-to-React flows passed. Visual browser review is separate.')
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == '__main__':
    main()
