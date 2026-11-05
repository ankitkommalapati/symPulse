"""Explicit, effective-dated crosswalks. Ambiguity never silently joins entities."""
from collections import defaultdict

from pulse.intelligence.rules import instant


class IdentityResolver:
    def __init__(self, mappings):
        self.index = defaultdict(list)
        self.used = {}
        self.cache = {}
        for row in mappings:
            self.index[(row["entity_type"], row["source_namespace"], row["source_entity_id"])].append(row)

    def resolve(self, kind, namespace, source_id, start, end, source_facility=None):
        key = (kind, namespace, source_id, str(start), str(end), source_facility)
        if key in self.cache:
            return self.cache[key]
        candidates = [row for row in self.index[(kind, namespace, source_id)]
                      if row["mapping_status"] in ("verified", "verified_demo_mapping")
                      and instant(row["valid_from"]) <= instant(start)
                      and instant(row["valid_to"]) > instant(start)
                      and instant(row["valid_to"]) >= instant(end)
                      and (source_facility is None or row.get("source_facility_id") == source_facility)]
        identities = {row["canonical_id"] for row in candidates}
        if len(identities) != 1:
            self.cache[key] = None
            return None
        for row in candidates:
            self.used[row["record_id"]] = row
        self.cache[key] = next(iter(identities))
        return self.cache[key]

    def unit(self, namespace, code, facility, start, end):
        return self.resolve("unit", namespace, code, start, end, facility)

    def facility(self, namespace, code, start, end):
        return self.resolve("facility", namespace, code, start, end)
