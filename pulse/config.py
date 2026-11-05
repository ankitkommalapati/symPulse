"""Explicit application configuration, resolved independently of working directory."""
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone offset")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    evidence_dir: Path
    as_of: str
    hospital_timezone: str
    host: str
    port: int
    workflow_path: Path

    @classmethod
    def load(cls, environ: Optional[Mapping[str, str]] = None, root: Path = ROOT):
        env = dict(dotenv_values(root / ".env"))
        env.update(os.environ if environ is None else environ)

        def setting(name, default):
            value = env.get(name, default)
            if value is None or not str(value).strip():
                raise ValueError("%s must not be empty" % name)
            return str(value).strip()

        def path(name, default):
            value = Path(setting(name, str(default))).expanduser()
            return (value if value.is_absolute() else root / value).resolve()

        data_dir = path("PULSE_DATA_DIR", "data/generated")
        as_of = utc_timestamp(setting("PULSE_AS_OF", "2026-11-05T14:00:00Z"))
        hospital_timezone = setting("PULSE_TIMEZONE", "America/Chicago")
        ZoneInfo(hospital_timezone)
        port = int(setting("PULSE_PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("PULSE_PORT must be between 1 and 65535")
        workflow_path = path('PULSE_WORKFLOW_PATH', 'data/workflow/pulse_workflow.sqlite')
        database_path = path('PULSE_DATABASE_PATH', data_dir / 'pulse_demo.sqlite')
        if workflow_path == database_path:
            raise ValueError('Workflow and source databases must have different paths')
        return cls(data_dir=data_dir,
                   database_path=path("PULSE_DATABASE_PATH", data_dir / "pulse_demo.sqlite"),
                   evidence_dir=path("PULSE_EVIDENCE_DIR", "data/evidence"),
                   as_of=as_of, hospital_timezone=hospital_timezone,
                   host=setting("PULSE_HOST", "127.0.0.1"), port=port, workflow_path=workflow_path)
