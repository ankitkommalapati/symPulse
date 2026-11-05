#!/usr/bin/env python3
"""Verify source and evidence requests through an actual HTTP listener."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = dict(os.environ, PULSE_PORT=str(port), PULSE_HOST="127.0.0.1")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, "-m", "pulse", "serve"], cwd=ROOT,
                                  env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            base = "http://127.0.0.1:" + str(port)

            def get(path):
                with urllib.request.urlopen(base + path, timeout=5) as response:
                    return json.load(response)

            for _ in range(50):
                if server.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                try:
                    get("/health/live")
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Service did not become live within five seconds")
            ready = get("/health/ready")
            if ready["status"] != "ready":
                raise RuntimeError("Service is not ready")
            sources = get("/api/sources")
            units = get("/api/units")
            if len(sources["items"]) != 21 or len(units["items"]) != 6:
                raise RuntimeError("Unexpected source inventory or unit count")
            evidence = get("/api/evidence/planning_context:units:ICU")
            artifact = get(evidence["artifact_url"])
            if artifact["record"] != evidence["record"]:
                raise RuntimeError("Evidence artifact does not match source snapshot")
            print(json.dumps({"live_http": "passed", "readiness": ready["status"],
                              "source_tables": len(sources["items"]), "units": len(units["items"]),
                              "evidence_round_trip": "passed"}))
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
