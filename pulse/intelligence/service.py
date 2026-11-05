"""Bounded analysis cache and persistent investigation snapshots."""
from collections import OrderedDict
from threading import Lock

from pulse.config import utc_timestamp
from pulse.intelligence.engine import IntelligenceEngine
from pulse.repository import DatasetUnavailable


class IntelligenceService:
    def __init__(self, repository, storage, timezone):
        self.repository, self.storage, self.timezone = repository, storage, timezone
        self.cache = OrderedDict()
        self.lock = Lock()

    def analysis(self, as_of):
        clock = utc_timestamp(as_of)
        try:
            stat = self.repository.path.stat()
        except OSError as exc:
            raise DatasetUnavailable("Source database is unavailable") from exc
        # Include the WAL generation when a writer is managing an existing archive.
        wal = self.repository.path.with_name(self.repository.path.name + "-wal")
        try:
            wal_stat = wal.stat()
            wal_key = (wal_stat.st_mtime_ns, wal_stat.st_size)
        except FileNotFoundError:
            wal_key = None
        key = (clock, stat.st_mtime_ns, stat.st_size, wal_key)
        with self.lock:
            if key not in self.cache:
                snapshot = self.repository.snapshot(clock)
                self.cache[key] = IntelligenceEngine(snapshot, clock, self.timezone).analyze()
                while len(self.cache) > 4:
                    self.cache.popitem(last=False)
            self.cache.move_to_end(key)
            return self.cache[key]

    def packet(self, investigation_id, as_of):
        analysis = self.analysis(as_of)
        packet = analysis["investigations"].get(investigation_id)
        if packet is None:
            return None
        digest = self.storage.put_json(packet)
        return {**packet, "snapshot_id": digest, "artifact_url": "/api/artifacts/" + digest}
