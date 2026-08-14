"""
backend/db/mongodb.py
Async MongoDB client for Burn-Ex.
Uses motor (async pymongo wrapper).
"""

import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


def get_mongo_uri() -> str:
    return os.environ.get("MONGO_URI", "")


def get_db_name() -> str:
    return os.environ.get("MONGO_DB_NAME", "burnex")


async def connect_db():
    """Initialize the MongoDB client. Call on app startup."""
    global _client, _database
    uri = get_mongo_uri()
    if not uri or "PLACEHOLDER" in uri:
        print("[MongoDB] WARNING: MONGO_URI not configured — MongoDB features will be unavailable.")
        return
    try:
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        _database = _client[get_db_name()]
        # Verify connectivity
        await _client.admin.command("ping")
        print(f"[MongoDB] Connected to database: {get_db_name()}")
    except Exception as e:
        print(f"[MongoDB] Connection failed: {e}")
        _client = None
        _database = None


async def close_db():
    """Close MongoDB client. Call on app shutdown."""
    global _client, _database
    if _client:
        _client.close()
        _client = None
        _database = None
        print("[MongoDB] Connection closed.")


def get_database() -> Optional[AsyncIOMotorDatabase]:
    """Return the active database instance, or None if not connected."""
    return _database


def is_connected() -> bool:
    return _database is not None
