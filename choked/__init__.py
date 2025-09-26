# choked/__init__.py

from .choked import Choked
from .token_bucket import RedisTokenBucket, ProxyTokenBucket

__version__ = "0.2.5"

# Choked class is the main interface - users create an instance with either:
# - choke = Choked(redis_url="redis://localhost:6379/0") for Redis backend
# - choke = Choked(api_token="your-token") for proxy service backend
# Then use the instance as a decorator: @choke(key="api", request_limit="10/s")

__all__ = [
    "Choked",
    "RedisTokenBucket", 
    "ProxyTokenBucket",
]