"""
Choked - A Python rate limiting library using token bucket algorithm.

This library provides decorators for rate limiting both synchronous and asynchronous functions,
with support for Redis-based distributed rate limiting and token-based estimation for AI APIs.
"""

from .choked import choked, get_token_bucket, ESTIMATORS
from .choked import default_estimator, voyageai_estimator, openai_estimator

__version__ = "0.2.1"
__all__ = [
    "choked",
    "get_token_bucket", 
    "ESTIMATORS",
    "default_estimator",
    "voyageai_estimator", 
    "openai_estimator"
]
