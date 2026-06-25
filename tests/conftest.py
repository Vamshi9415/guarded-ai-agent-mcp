import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.pop("SSLKEYLOGFILE", None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeCursor(list):
    def sort(self, key, direction):
        reverse = direction == -1
        return FakeCursor(sorted(self, key=lambda item: item.get(key), reverse=reverse))

    def limit(self, count):
        return FakeCursor(self[:count])


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.indexes = []
        self.inserted = []
        self.deleted = []
        self.updated = []

    def create_index(self, spec):
        self.indexes.append(spec)
        return "idx"

    def insert_one(self, doc):
        stored = dict(doc)
        stored.setdefault("_id", f"id-{len(self.docs) + 1}")
        self.docs.append(stored)
        self.inserted.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._matches(doc, query):
                if projection:
                    return {key: doc[key] for key, include in projection.items() if include and key in doc}
                return doc
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        rows = []
        for doc in self.docs:
            if self._matches(doc, query):
                row = dict(doc)
                if projection and projection.get("_id") == 0:
                    row.pop("_id", None)
                rows.append(row)
        return FakeCursor(rows)

    def update_one(self, query, update):
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                self.updated.append((query, update))
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.deleted.append(self.docs.pop(index))
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def count_documents(self, query):
        return sum(1 for doc in self.docs if self._matches(doc, query))

    def _matches(self, doc, query):
        return all(self._value_matches(doc.get(key), expected) for key, expected in query.items())

    def _value_matches(self, actual, expected):
        if isinstance(expected, dict) and "$in" in expected:
            return actual in expected["$in"]
        return actual == expected


@pytest.fixture
def fake_collection():
    return FakeCollection
