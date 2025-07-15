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
    token = os.getenv("CHOKED_API_TOKEN")
    if token:
        return ProxyTokenBucket(token, key, max_tokens, max_tokens / refill_period)
    else:
        return RedisTokenBucket(key, max_tokens, max_tokens / refill_period)