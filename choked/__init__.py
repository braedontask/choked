# choked/__init__.py

from .choked import Choked
from .token_bucket import RedisTokenBucket

__version__ = "0.2.4"

# Choked class is the main interface - users can do `import choked` and use `choked.Choked`
# or they can do `from choked import Choked` and use `Choked` directly

__all__ = [
    "Choked",
    "RedisTokenBucket",
]