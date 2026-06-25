import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


def get_mongo_db_name() -> str:
    return os.environ.get("MONGO_DB_NAME", "guarded_ai")


def get_mongo_uri() -> str:
    explicit_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    if explicit_uri:
        return explicit_uri

    mongo_type = os.environ.get("MONGO_TYPE", "local").lower()
    if mongo_type == "atlas":
        user = quote_plus(os.environ["MONGO_USER"])
        password = quote_plus(os.environ["MONGO_PASS"])
        host = os.environ["MONGO_HOST_URI"]
        auth_source = os.environ.get("MONGO_AUTH_SRC", get_mongo_db_name())
        write_concern = os.environ.get("MONGO_W", "majority")
        app_name = os.environ.get("MONGO_APP_NAME", "Clusterwms")
        # connectTimeoutMS and socketTimeoutMS added to avoid hanging on
        # DNS / network failures when connecting to Atlas.
        return (
            f"mongodb+srv://{user}:{password}@{host}/"
            f"?authSource={quote_plus(auth_source)}"
            f"&retryWrites=true"
            f"&w={quote_plus(write_concern)}"
            f"&appName={quote_plus(app_name)}"
            f"&connectTimeoutMS=5000"
            f"&socketTimeoutMS=10000"
        )
    return os.environ.get("MONGO_LOCAL_URI", "mongodb://localhost:27017")


def get_mongo_heartbeat_ms() -> int:
    return int(os.environ.get("MONGO_HEARTBEAT_MS", "60000"))
