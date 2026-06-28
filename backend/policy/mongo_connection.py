"""MongoDB connection helpers for policy persistence."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from pymongo import MongoClient


@dataclass(frozen=True)
class MongoSettings:
    user: str
    password: str
    host_uri: str
    db_name: str
    app_name: str

    @classmethod
    def from_env(cls) -> "MongoSettings":
        missing = [
            name
            for name in ("MONGO_USER", "MONGO_PASS", "MONGO_HOST_URI", "MONGO_DB_NAME", "MONGO_APP_NAME")
            if not os.getenv(name)
        ]
        if missing:
            raise RuntimeError(f"Missing Mongo environment variables: {', '.join(missing)}")

        return cls(
            user=os.environ["MONGO_USER"],
            password=os.environ["MONGO_PASS"],
            host_uri=os.environ["MONGO_HOST_URI"],
            db_name=os.environ["MONGO_DB_NAME"],
            app_name=os.environ["MONGO_APP_NAME"],
        )

    def uri(self) -> str:
        return (
            f"mongodb+srv://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host_uri}/"
            f"?retryWrites=true&w=majority&appName={quote_plus(self.app_name)}"
        )


def create_mongo_client() -> MongoClient:
    """Creates a configured MongoDB client from environment variables."""
    settings = MongoSettings.from_env()
    return MongoClient(settings.uri(), serverSelectionTimeoutMS=5000)
