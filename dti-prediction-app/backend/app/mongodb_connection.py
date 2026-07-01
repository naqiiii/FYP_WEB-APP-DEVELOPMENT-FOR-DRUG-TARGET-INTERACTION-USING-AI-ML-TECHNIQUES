from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure
import asyncio
import os
import json
import uuid
from datetime import datetime
from pathlib import Path

from app.settings import MONGODB_URL, DATABASE_NAME

BASE_DIR = Path(__file__).resolve().parent.parent

# Global connection state
mongodb_client = None
database = None

# -------------------------------------------------------------------
# Mock Async Database implementation for offline fallback
# -------------------------------------------------------------------
class MockCursor:
    def __init__(self, data):
        self.data = data
        self.index = 0

    def sort(self, field, direction=1):
        reverse = (direction == -1)
        try:
            # Sort by field. Handle datetime or string comparison
            self.data = sorted(self.data, key=lambda x: x.get(field, ""), reverse=reverse)
        except Exception as e:
            print(f"[Mock DB Warning] Sorting failed: {e}")
        return self

    def skip(self, n):
        self.data = self.data[n:]
        return self

    def limit(self, n):
        self.data = self.data[:n]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index < len(self.data):
            val = self.data[self.index]
            self.index += 1
            return val
        else:
            raise StopAsyncIteration

class MockCollection:
    def __init__(self, db_instance, collection_name):
        self.db = db_instance
        self.name = collection_name

    def _get_data(self):
        return self.db._load_collection(self.name)

    def _save_data(self, data):
        self.db._save_collection(self.name, data)

    async def find_one(self, query):
        data = self._get_data()
        for doc in data:
            if self._matches(doc, query):
                return doc
        return None

    async def insert_one(self, doc):
        data = self._get_data()
        doc = dict(doc)
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        data.append(doc)
        self._save_data(data)
        
        class InsertResult:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return InsertResult(doc["_id"])

    async def insert_many(self, docs):
        data = self._get_data()
        inserted_ids = []
        for doc in docs:
            doc = dict(doc)
            if "_id" not in doc:
                doc["_id"] = str(uuid.uuid4())
            data.append(doc)
            inserted_ids.append(doc["_id"])
        self._save_data(data)
        return inserted_ids

    async def update_one(self, query, update):
        data = self._get_data()
        modified_count = 0
        for doc in data:
            if self._matches(doc, query):
                if "$set" in update:
                    for k, v in update["$set"].items():
                        doc[k] = v
                    modified_count = 1
                    break
        if modified_count > 0:
            self._save_data(data)
            
        class UpdateResult:
            def __init__(self, count):
                self.modified_count = count
        return UpdateResult(modified_count)

    async def count_documents(self, query):
        data = self._get_data()
        count = 0
        for doc in data:
            if self._matches(doc, query):
                count += 1
        return count

    def find(self, query):
        data = self._get_data()
        matching = []
        for doc in data:
            if self._matches(doc, query):
                matching.append(doc)
        return MockCursor(matching)

    async def create_index(self, keys, **kwargs):
        pass

    async def drop_index(self, name):
        pass

    def _matches(self, doc, query):
        for k, v in query.items():
            doc_val = doc.get(k)
            # Handle ObjectId conversion and comparison
            if type(v).__name__ == "ObjectId":
                v = str(v)
            if type(doc_val).__name__ == "ObjectId":
                doc_val = str(doc_val)
            
            if doc_val != v:
                return False
        return True

class MockAsyncDatabase:
    def __init__(self, filepath="mock_database.json"):
        self.filepath = filepath
        self._collections = {}

    def _load_all(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                    return self._deserialize(data)
            except Exception as e:
                print(f"[Mock DB] Error loading mock database file: {e}")
        return {}

    def _save_all(self, data):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self._serialize(data), f, indent=2)
        except Exception as e:
            print(f"[Mock DB] Error saving mock database file: {e}")

    def _load_collection(self, name):
        all_data = self._load_all()
        return all_data.get(name, [])

    def _save_collection(self, name, col_data):
        all_data = self._load_all()
        all_data[name] = col_data
        self._save_all(all_data)

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection(self, name)
        return self._collections[name]

    def _serialize(self, obj):
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize(i) for i in obj]
        elif isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        elif type(obj).__name__ == "ObjectId":
            return {"__objectid__": str(obj)}
        else:
            return obj

    def _deserialize(self, obj):
        if isinstance(obj, dict):
            if "__datetime__" in obj:
                return datetime.fromisoformat(obj["__datetime__"])
            if "__objectid__" in obj:
                return obj["__objectid__"]
            return {k: self._deserialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deserialize(i) for i in obj]
        else:
            return obj

# -------------------------------------------------------------------
# MongoDB Index and connection management
# -------------------------------------------------------------------
def _index_name(keys, name=None):
    if name:
        return name
    return "_".join(f"{field}_{direction}" for field, direction in keys)


async def _ensure_index(collection, keys, **kwargs):
    """Create an index, replacing it when an existing one has conflicting specs."""
    try:
        await collection.create_index(keys, **kwargs)
    except OperationFailure as e:
        if e.code != 86:  # IndexKeySpecsConflict
            raise
        await collection.drop_index(_index_name(keys, kwargs.get("name")))
        await collection.create_index(keys, **kwargs)


async def connect_to_mongodb():
    """Establish connection to MongoDB Atlas, local MongoDB, or JSON fallback."""
    global mongodb_client, database

    print("Connecting to MongoDB Atlas...")
    try:
        client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000, # Faster timeout for diagnostics
            connectTimeoutMS=5000,
            socketTimeoutMS=None,
            retryWrites=True,
            maxPoolSize=50,
            minPoolSize=10,
        )
        # Test Atlas connection immediately
        await asyncio.wait_for(client.server_info(), timeout=5)
        mongodb_client = client
        database = mongodb_client[DATABASE_NAME]
        print(f"Connected to MongoDB Atlas database: {DATABASE_NAME}")
    except Exception as atlas_exc:
        print(f"[Warning] Atlas connection failed: {atlas_exc}")
        print("Attempting connection to Local MongoDB (127.0.0.1:27017)...")
        
        try:
            local_url = "mongodb://127.0.0.1:27017"
            client = AsyncIOMotorClient(
                local_url,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
            )
            # Test local connection
            await asyncio.wait_for(client.server_info(), timeout=3)
            mongodb_client = client
            database = mongodb_client[DATABASE_NAME]
            print(f"Connected to Local MongoDB database: {DATABASE_NAME}")
        except Exception as local_exc:
            print(f"[Warning] Local MongoDB connection failed: {local_exc}")
            print("Falling back to local file-based Mock JSON database...")
            
            # Setup JSON Mock Database
            mongodb_client = None
            database = MockAsyncDatabase(filepath=str(BASE_DIR / "mock_database.json"))
            print(f"Using local mock database file at: {BASE_DIR}/mock_database.json")
            return

    # Ensure indexes (only runs on actual MongoDB client, local or remote)
    try:
        await _ensure_index(
            database["prediction_history"],
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
        )
        await _ensure_index(
            database["users"],
            [("email", ASCENDING)],
            unique=True,
        )
    except Exception as index_exc:
        print(f"[Warning] Failed to construct collection indexes: {index_exc}")


async def close_mongodb_connection():
    """Close MongoDB connection."""
    global mongodb_client

    if mongodb_client:
        print("Closing MongoDB connection...")
        mongodb_client.close()
    else:
        print("Mock Database closed.")


def get_database():
    """Return active database instance."""
    if database is None:
        raise RuntimeError("Database is not initialized.")
    return database


def get_database_status():
    """Database health information."""
    is_mock = isinstance(database, MockAsyncDatabase)
    return {
        "connected": database is not None,
        "using_mongodb": mongodb_client is not None,
        "database_name": "mock_database.json" if is_mock else DATABASE_NAME,
        "mode": "mock_json" if is_mock else ("local_mongodb" if "127.0.0.1" in MONGODB_URL or "localhost" in MONGODB_URL else "atlas_mongodb")
    }