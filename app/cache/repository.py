class MemoryCache:
    def __init__(self): self._store = {}
    def get(self, key): return self._store.get(key)
    def set(self, key, value): self._store[key] = value
    def delete(self, key): self._store.pop(key, None)
cache = MemoryCache()  # TODO: replace with Redis adapter.
