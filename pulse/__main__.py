"""Run with python -m pulse prepare|check|serve."""
import argparse
import hashlib
import json
import subprocess
import sys

from pulse.config import ROOT, Settings
from pulse.repository import SourceRepository
from pulse.storage import EvidenceStore
from pulse.workflows.store import WorkflowStore


def prepare(settings):
    required = (settings.data_dir / "manifest.json", settings.database_path)
    if not any(p.exists() for p in required):
        if settings.database_path != settings.data_dir / "pulse_demo.sqlite":
            raise ValueError("Generate the dataset first when using a separate PULSE_DATABASE_PATH")
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_data.py"),
                        "--output", str(settings.data_dir)], check=True)
    elif not all(p.is_file() for p in required):
        raise ValueError("Dataset is incomplete; restore the missing files or generate into a new PULSE_DATA_DIR")
    subprocess.run([sys.executable, str(ROOT / "scripts/validate_data.py"),
                    "--data-dir", str(settings.data_dir), "--database-path", str(settings.database_path)], check=True)
    check(settings)
    manifest = (settings.data_dir / "manifest.json").read_bytes()
    digest = EvidenceStore(settings.evidence_dir).put_json({
        "kind": "dataset_manifest", "manifest": json.loads(manifest),
        "manifest_sha256": hashlib.sha256(manifest).hexdigest()})
    print(json.dumps({"status": "prepared", "dataset_manifest_evidence_id": digest}))


def check(settings):
    SourceRepository(settings.database_path).check()
    EvidenceStore(settings.evidence_dir).check()
    WorkflowStore(settings.workflow_path).check()
    print(json.dumps({"status": "ready", "as_of": settings.as_of}))


def main():
    parser = argparse.ArgumentParser(description="symplr Pulse service")
    parser.add_argument("command", choices=("prepare", "check", "serve"))
    args = parser.parse_args()
    try:
        settings = Settings.load()
        if args.command == "prepare":
            prepare(settings)
        elif args.command == "check":
            check(settings)
        else:
            import uvicorn
            from pulse.api import create_app
            uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, "Pulse: %s\n" % exc)


if __name__ == "__main__":
    main()
