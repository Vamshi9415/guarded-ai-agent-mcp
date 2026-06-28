from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from backend.policy.mongo_connection import MongoSettings, create_mongo_client


load_dotenv()

try:
    print("Connecting to MongoDB Atlas...")

    settings = MongoSettings.from_env()
    print("User:", settings.user)
    print("Host:", settings.host_uri)
    print("DB:", settings.db_name)
    print("Password loaded:", bool(settings.password))
    print(
        f"mongodb+srv://{settings.user}:******@{settings.host_uri}/?retryWrites=true&w=majority&appName={settings.app_name}"
    )

    client = create_mongo_client()

    # Verify connection
    client.admin.command("ping")
    print("✅ Successfully connected to MongoDB Atlas!")

    db = client[settings.db_name]

    collections = db.list_collection_names()

    print(f"\nDatabase: {settings.db_name}")
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