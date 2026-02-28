from __future__ import annotations

import pytest
import os
from app.container import container
from pymongo import MongoClient
import redis

@pytest.fixture(scope="session", autouse=True)
def init_test_services():
    mongodb_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/commerce_test")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    container.mongo_manager.uri = mongodb_uri
    container.mongo_manager.enabled = True
    container.redis_manager.url = redis_url
    container.redis_manager.enabled = True
    
    container.mongo_manager.connect()
    container.redis_manager.connect()
    
    # Clean DB before tests
    if container.mongo_manager.client:
        container.mongo_manager.client.drop_database("commerce_test")
    if container.redis_manager.client:
        container.redis_manager.client.flushdb()
    
    yield
    if getattr(container.mongo_manager, "client", None):
        container.mongo_manager.client.close()
    if getattr(container.redis_manager, "client", None):
        container.redis_manager.client.close()

@pytest.fixture(autouse=True)
def reset_db_state():
    # If necessary, we can clean up between tests here, but for now integration tests 
    # might expect clean slate or manage their own records via unique IDs.
    pass
