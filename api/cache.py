import time
import uuid
import threading
import pandas as pd


class UploadCache:
    """In-memory cache for uploaded DataFrames, keyed by upload ID with TTL."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[float, pd.DataFrame]] = {}
        self._lock = threading.Lock()

    def store(self, df: pd.DataFrame) -> str:
        uid = uuid.uuid4().hex[:12]
        with self._lock:
            self._entries[uid] = (time.time(), df)
        return uid

    def get(self, upload_id: str) -> pd.DataFrame | None:
        with self._lock:
            entry = self._entries.get(upload_id)
            if entry is None:
                return None
            timestamp, df = entry
            if time.time() - timestamp > self.ttl_seconds:
                del self._entries[upload_id]
                return None
            return df

    def cleanup(self) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            expired = [
                uid
                for uid, (ts, _) in self._entries.items()
                if now - ts > self.ttl_seconds
            ]
            for uid in expired:
                del self._entries[uid]
                removed += 1
        return removed
