import os
import time
import functools
import inspect
import asyncio
import random
from dotenv import load_dotenv
from typing import Any, Callable
from .token_bucket.redis_token_bucket import RedisTokenBucket
from .token_bucket.proxy_token_bucket import ProxyTokenBucket

load_dotenv()

def choked(key: str, max_tokens: int, refill_period: int, sleep_time: float = 1.0) -> Callable:
    """
    A rate limiting decorator using token bucket algorithm.
    
    This decorator applies rate limiting to both synchronous and asynchronous functions.
    When the rate limit is exceeded, the function will sleep with exponential backoff
    and jitter until tokens become available.
    
    Args:
        key (str): Unique identifier for the rate limit bucket. Functions with the same
            key share the same rate limit.
        max_tokens (int): Maximum number of tokens in the bucket. This represents the
            burst capacity - how many requests can be made immediately.
        refill_period (int): Time in seconds for the bucket to completely refill from
            empty to max_tokens. The refill rate is max_tokens/refill_period per second.
        sleep_time (float, optional): Initial sleep time in seconds when rate limited.
            Uses exponential backoff with jitter. Defaults to 1.0.
    
    Returns:
        Callable: A decorator function that can be applied to sync or async functions.
    
    Examples:
        Basic usage:
        ```python
        @choked(key="api_calls", max_tokens=10, refill_period=60)
        def make_api_call():
            # This function is rate limited to 10 calls per minute
            pass
        
        @choked(key="db_writes", max_tokens=5, refill_period=1, sleep_time=0.5)
        async def write_to_db():
            # This async function is rate limited to 5 calls per second
            pass
        ```
    
    Note:
        - The decorator automatically detects if the wrapped function is async or sync
        - Uses Redis for distributed rate limiting if CHOKED_API_TOKEN is not set
        - Uses proxy service for rate limiting if CHOKED_API_TOKEN environment variable is set
        - Sleep time increases exponentially (doubles) on each retry with random jitter (0.8x to 1.2x)
    """
    def decorator(func: Callable) -> Callable:
        bucket = get_token_bucket(key, max_tokens, refill_period)
        
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_sleep = sleep_time
            while not await bucket.acquire():
                jitter = random.uniform(0.8, 1.2)
                actual_sleep = current_sleep * jitter
                await asyncio.sleep(actual_sleep)
                current_sleep = current_sleep * 2
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_sleep = sleep_time
            while not asyncio.run(bucket.acquire()):
                jitter = random.uniform(0.8, 1.2)
                actual_sleep = current_sleep * jitter
                time.sleep(actual_sleep)
                current_sleep = current_sleep * 2
            return func(*args, **kwargs)
        
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def get_token_bucket(key: str, max_tokens: int, refill_period: int) -> Callable:
    """
    Factory function to create the appropriate token bucket implementation.
    
    This function determines whether to use a Redis-based token bucket for local/distributed
    rate limiting or a proxy-based token bucket for managed rate limiting service.
    
    Args:
        key (str): Unique identifier for the rate limit bucket.
        max_tokens (int): Maximum number of tokens in the bucket (burst capacity).
        refill_period (int): Time in seconds for the bucket to refill completely.
    
    Returns:
        Callable: Either a RedisTokenBucket or ProxyTokenBucket instance depending on
            whether CHOKED_API_TOKEN environment variable is set.
    
    Environment Variables:
        CHOKED_API_TOKEN: If set, uses ProxyTokenBucket with this token for authentication.
            If not set, uses RedisTokenBucket for local Redis-based rate limiting.
    
    Examples:
        ```python
        # This will use Redis if CHOKED_API_TOKEN is not set
        bucket = get_token_bucket("my_key", 10, 60)
        
        # Set environment variable to use proxy service
        os.environ["CHOKED_API_TOKEN"] = "your_api_token"
        bucket = get_token_bucket("my_key", 10, 60)  # Uses proxy service
        ```
    """
    token = os.getenv("CHOKED_API_TOKEN")
    if token:
        return ProxyTokenBucket(token, key, max_tokens, max_tokens / refill_period)
    else:
        return RedisTokenBucket(key, max_tokens, max_tokens / refill_period)