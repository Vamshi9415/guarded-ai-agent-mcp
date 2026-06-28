import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Load environment variables
load_dotenv()

MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASS = os.getenv("MONGO_PASS")
MONGO_HOST_URI = os.getenv("MONGO_HOST_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_APP_NAME = os.getenv("MONGO_APP_NAME")

print("User:", MONGO_USER)
print("Host:", MONGO_HOST_URI)
print("DB:", MONGO_DB_NAME)
print("Password loaded:", bool(MONGO_PASS))

# Build MongoDB URI
MONGO_URI = (
    f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}"
    f"@{MONGO_HOST_URI}/"
    f"?retryWrites=true&w=majority&appName={MONGO_APP_NAME}"
)
print(
    f"mongodb+srv://{MONGO_USER}:******@{MONGO_HOST_URI}/?retryWrites=true&w=majority&appName={MONGO_APP_NAME}"
)
try:
    print("Connecting to MongoDB Atlas...")

    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
    )

    # Verify connection
    client.admin.command("ping")
    print("✅ Successfully connected to MongoDB Atlas!")

    db = client[MONGO_DB_NAME]

    collections = db.list_collection_names()

    print(f"\nDatabase: {MONGO_DB_NAME}")
    print(f"Collections ({len(collections)}):")

    if collections:
        for collection in collections:
            print(f"  • {collection}")
    else:
        print("  No collections found.")

except ServerSelectionTimeoutError as e:
    print(f"❌ Server selection timeout:\n{e}")

except ConnectionFailure as e:
    print(f"❌ Connection failed:\n{e}")

except Exception as e:
    print(f"❌ Unexpected error:\n{e}")

finally:
    try:
        client.close()
    except NameError:
        pass