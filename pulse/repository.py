"""Read-only source repository with availability-first version selection."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from pulse.config import utc_timestamp

TABLES = frozenset({
    "access_policy_requirements", "employee_qualifications", "employees", "entity_crosswalk",
    "facilities", "paid_time", "physician_assignments", "privilege_grants", "providers",
    "quality_events", "renewal_cases", "service_dependencies", "staffing_requirements",
    "unavailability", "unit_activity", "units", "vendor_credentials", "vendor_representatives",
    "vendor_visits", "vendors", "workforce_assignments",
})
JSON_FIELDS = {"eligible_org_codes"}
BOOL_FIELDS = {"synthetic", "is_deleted", "required", "reporting_campaign"}


class DatasetUnavailable(RuntimeError):
    pass


class SourceRepository:
    def __init__(self, database_path: Path):
        self.path = database_path.resolve()

    @contextmanager
    def connect(self):
        try:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        except sqlite3.Error as exc:
            raise DatasetUnavailable("Source database is unavailable; run python -m pulse prepare") from exc
        connection.row_factory = sqlite3.Row
        connection.create_function("pulse_utc", 1, utc_timestamp, deterministic=True)
        try:
            yield connection
        except sqlite3.DatabaseError as exc:
            raise DatasetUnavailable("Source database could not be read") from exc
        finally:
            connection.close()

    @staticmethod
    def _table(table):
        if table not in TABLES:
            raise ValueError("Unknown source table")
        return '"%s"' % table

    @staticmethod
    def _decode(row):
        result = dict(row)
        result.pop("_revision_rank", None)
        for key in JSON_FIELDS & result.keys():
            result[key] = json.loads(result[key]) if result[key] is not None else None
        for key in BOOL_FIELDS & result.keys():
            result[key] = bool(result[key])
        return result

    def _known_sql(self, table):
        return """WITH known AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY record_id ORDER BY record_version DESC
            ) AS _revision_rank FROM %s
            WHERE pulse_utc(available_at) <= ?
        ) SELECT * FROM known WHERE _revision_rank = 1 AND is_deleted = 0""" % self._table(table)

    def records(self, table: str, as_of: str, limit: int = 100, offset: int = 0):
        clock = utc_timestamp(as_of)
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("Invalid pagination")
        sql = self._known_sql(table) + " ORDER BY record_id LIMIT ? OFFSET ?"
        with self.connect() as conn:
            return [self._decode(row) for row in conn.execute(sql, (clock, limit, offset)).fetchall()]

    def record(self, record_id: str, as_of: str) -> Optional[dict]:
        parts = record_id.split(":", 2)
        if len(parts) != 3:
            raise ValueError("Invalid record identity")
        sql = self._known_sql(parts[1]) + " AND record_id = ?"
        with self.connect() as conn:
            row = conn.execute(sql, (utc_timestamp(as_of), record_id)).fetchone()
            return self._decode(row) if row else None

    def inventory(self, as_of):
        inventory = []
        with self.connect() as conn:
            for table in sorted(TABLES):
                sql = "SELECT COUNT(*) FROM (%s)" % self._known_sql(table)
                count = conn.execute(sql, (utc_timestamp(as_of),)).fetchone()[0]
                total = conn.execute("SELECT COUNT(*) FROM " + self._table(table)).fetchone()[0]
                inventory.append({"table": table, "known_records": count, "archive_record_versions": total})
        return inventory

    def snapshot(self, as_of: str):
        """Read all operational inputs in one consistent transaction, without pagination."""
        clock = utc_timestamp(as_of)
        with self.connect() as conn:
            conn.execute("BEGIN")
            return {table: [self._decode(row) for row in conn.execute(
                self._known_sql(table) + " ORDER BY record_id", (clock,)).fetchall()]
                for table in sorted(TABLES)}

    def check(self):
        with self.connect() as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise DatasetUnavailable("Source database integrity check failed")
            existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not TABLES <= existing:
                raise DatasetUnavailable("Source database is missing required tables")
            for table in TABLES:
                columns = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % self._table(table))}
                if not {"record_id", "record_version", "available_at", "is_deleted"} <= columns:
                    raise DatasetUnavailable("Source table is missing required version fields")
