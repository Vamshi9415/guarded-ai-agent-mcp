import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_mongodb_connection():
    # 1. Get the URI from environment variables
    mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    
    if not mongo_uri:
        print("❌ Error: MONGODB_URI or MONGO_URI not found in your .env file.")
        return

    print("🔄 Attempting to connect to MongoDB...")
    
    try:
        # 2. Initialize the client with a short timeout so it doesn't hang forever
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # 3. The admin 'ping' command forces a connection request
        client.admin.command('ping')
        
        print("✅ Success! Successfully connected to MongoDB.")
        
        # Optional: Print available databases to confirm access
        db_names = client.list_database_names()
        print(f"📂 Available databases: {db_names}")
        
    except ConfigurationError as ce:
        print("\n❌ Configuration Error!")
        print(f"Details: {ce}")
        print("\n💡 Tip: This usually means there is a DNS issue, an invalid connection string format, or a blocked SRV record on your local network.")
        
    except ConnectionFailure as cf:
        print("\n❌ Connection Failure!")
        print(f"Details: {cf}")
        print("\n💡 Tip: Check if your IP address is whitelisted in the MongoDB Atlas Network Access settings, or if your internet connection is stable.")
        
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_mongodb_connection()