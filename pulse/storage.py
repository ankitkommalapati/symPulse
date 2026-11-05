"""Immutable, content-addressed JSON evidence objects."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


class EvidenceStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, digest: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid evidence digest")
        target = self.root / digest[:2] / (digest + ".json")
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Evidence path escapes storage root")
        return target

    def put_json(self, document: dict) -> str:
        data = json.dumps(document, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        target = self._path(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if target.read_bytes() == data:
                return digest
        except FileNotFoundError:
            pass
        # Atomic replacement also repairs a damaged object with its original content.
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temp_name = stream.name
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
        return digest

    def get_json(self, digest: str) -> dict:
        data = self._path(digest).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Evidence integrity check failed")
        return json.loads(data)

    def check(self):
        digest = self.put_json({"kind": "storage_health", "schema_version": 1})
        self.get_json(digest)
