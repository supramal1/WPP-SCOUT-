import time
import pandas as pd
from api.cache import UploadCache


def test_store_and_retrieve():
    cache = UploadCache(ttl_seconds=3600)
    df = pd.DataFrame({"a": [1, 2, 3]})
    uid = cache.store(df)
    assert uid is not None
    retrieved = cache.get(uid)
    assert retrieved is not None
    pd.testing.assert_frame_equal(retrieved, df)


def test_get_missing_returns_none():
    cache = UploadCache(ttl_seconds=3600)
    assert cache.get("nonexistent") is None


def test_expired_entry_returns_none():
    cache = UploadCache(ttl_seconds=0)
    df = pd.DataFrame({"a": [1]})
    uid = cache.store(df)
    time.sleep(0.01)
    assert cache.get(uid) is None


def test_cleanup_removes_expired():
    cache = UploadCache(ttl_seconds=0)
    df = pd.DataFrame({"a": [1]})
    cache.store(df)
    cache.store(df)
    time.sleep(0.01)
    removed = cache.cleanup()
    assert removed >= 2
    assert len(cache._entries) == 0
