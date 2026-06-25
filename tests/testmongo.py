import os

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ConnectionFailure


load_dotenv()


@pytest.mark.integration
def test_mongodb_connection():
    if os.environ.get("RUN_MONGO_INTEGRATION") != "1":
        pytest.skip("Set RUN_MONGO_INTEGRATION=1 to run the real MongoDB connectivity check")

    mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    if not mongo_uri:
        pytest.fail("MONGODB_URI or MONGO_URI not found in environment")

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        assert client.list_database_names() is not None
    except (ConfigurationError, ConnectionFailure) as exc:
        pytest.fail(f"MongoDB connectivity check failed: {exc}")
