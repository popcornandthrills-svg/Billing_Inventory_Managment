import os
from functools import lru_cache
from pymongo import MongoClient
from pymongo.errors import PyMongoError


@lru_cache(maxsize=1)
def _client():
    uri = (os.getenv("MONGODB_URI") or "").strip()
    if not uri:
        raise RuntimeError("MONGODB_URI is not set")
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def is_configured() -> bool:
    return bool((os.getenv("MONGODB_URI") or "").strip() and (os.getenv("MONGODB_DB_NAME") or "").strip())


def get_db():
    name = (os.getenv("MONGODB_DB_NAME") or "").strip()
    if not name:
        raise RuntimeError("MONGODB_DB_NAME is not set")
    return _client()[name]


def ping() -> bool:
    try:
        _client().admin.command("ping")
        return True
    except PyMongoError:
        return False


def collection(name: str):
    return get_db()[str(name).strip()]
