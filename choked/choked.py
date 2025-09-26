import os
import time
import functools
import inspect
import asyncio
import random
import re
from dotenv import load_dotenv
from typing import Any, Callable, Optional, Union
from .token_bucket import RedisTokenBucket, ProxyTokenBucket

os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

import tiktoken
from transformers import AutoTokenizer

load_dotenv()

def parse_rate_limit(rate_str: Optional[str]) -> tuple[int, float]:
    """
    Parse rate limit string in format 'number/period' where period is 's' or 'm'.
    
    Args:
        rate_str: Rate string like '1000/s', '10000/m', or None
        
    Returns:
        Tuple of (max_capacity, refill_rate_per_second)
        Returns (0, 0.0) for None input (effectively no limit)
        
    Raises:
        ValueError: If rate_str format is invalid
    """
    if rate_str is None:
        return (0, 0.0)
    
    pattern = r'^(\d+)/(s|m)$'
    match = re.match(pattern, rate_str.strip())
    
    if not match:
        raise ValueError(f"Invalid rate format '{rate_str}'. Expected format: 'number/s' or 'number/m' (e.g., '1000/s', '10000/m')")
    
    number = int(match.group(1))
    period = match.group(2)
    
    if period == 's':
        return (number, float(number))
    elif period == 'm':
        return (number, float(number) / 60.0)
    
    raise ValueError(f"Invalid period '{period}'. Must be 's' or 'm'")


def default_estimator(*args, **kwargs) -> int:
    """Default token estimator using tiktoken."""
    texts = _extract_text_from_args(*args, **kwargs)
    if not texts:
        return 1
    
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
        total_tokens = sum(len(encoding.encode(text)) for text in texts)
        return total_tokens
    except Exception:
        return _word_based_estimation(*args, **kwargs)


def voyageai_estimator(*args, **kwargs) -> int:
    """VoyageAI token estimator using HuggingFace tokenizer."""
    texts = _extract_text_from_args(*args, **kwargs)
    if not texts:
        return 1
    
    try:
        tokenizer = AutoTokenizer.from_pretrained('voyageai/voyage-3.5')
        total_tokens = sum(len(tokenizer.encode(text)) for text in texts)
        return total_tokens
    except Exception:
        return default_estimator(*args, **kwargs)


def openai_estimator(*args, **kwargs) -> int:
    """OpenAI token estimator - uses default tiktoken estimator."""
    return default_estimator(*args, **kwargs)


def _extract_text_from_args(*args, **kwargs) -> list[str]:
    """Extract text strings from function arguments."""
    texts = []
    
    for key, value in kwargs.items():
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, list):
            texts.extend([str(item) for item in value if isinstance(item, str)])
        elif isinstance(value, dict) and key == 'messages':
            # Handle OpenAI chat messages format
            for msg in value:
                if isinstance(msg, dict) and 'content' in msg:
                    texts.append(str(msg['content']))
    
    for arg in args:
        if isinstance(arg, str):
            texts.append(arg)
        elif isinstance(arg, list):
            texts.extend([str(item) for item in arg if isinstance(item, str)])
    
    return texts


def _word_based_estimation(*args, **kwargs) -> int:
    """Fallback word-based token estimation (~0.75 tokens per word)."""
    texts = _extract_text_from_args(*args, **kwargs)
    if not texts:
        return 1
    
    total_words = sum(len(text.split()) for text in texts)
    return max(1, int(total_words * 0.75))


ESTIMATORS = {
    'voyageai': voyageai_estimator,
    'openai': openai_estimator,
    'default': default_estimator,
}


def choked(key: str, request_limit: Optional[str] = None, token_limit: Optional[str] = None, token_estimator: Optional[str] = None) -> Callable:
    """
    A dual rate limiting decorator using token bucket algorithm for both requests and tokens.
    
    This decorator applies rate limiting to both synchronous and asynchronous functions.
    It enforces both request-based and token-based limits simultaneously. When either
    limit is exceeded, the function will sleep with exponential backoff and jitter.
    
    Args:
        key (str): Unique identifier for the rate limit bucket. Functions with the same
            key share the same rate limit.
        request_limit (str, optional): Request rate limit in format 'number/period'.
            Examples: '100/s' (100 per second), '6000/m' (6000 per minute).
            If None, no request limiting is applied.
        token_limit (str, optional): Token rate limit in format 'number/period'.
            Examples: '1000/s' (1000 tokens per second), '100000/m' (100K tokens per minute).
            If None, no token limiting is applied.
        token_estimator (str, optional): Token estimation method. Options:
            - None: Only request-based limiting (ignores token limits)
            - 'voyageai': Use VoyageAI tokenizer for text estimation
            - 'openai': Use OpenAI/tiktoken for text estimation
            - 'default'/'tiktoken': Use tiktoken with GPT-4 tokenizer
    
    Returns:
        Callable: A decorator function that can be applied to sync or async functions.
    
    Examples:
        Request-only limiting:
        ```python
        @choked(key="api_calls", request_limit="10/s")
        def make_api_call():
            # This function is rate limited to 10 requests per second
            pass
        ```
        
        Token-only limiting for VoyageAI:
        ```python
        @choked(key="voyage_embed", token_limit="1000000/m", token_estimator="voyageai")
        def get_embeddings(texts, model="voyage-3"):
            # Rate limited by estimated tokens (1M per minute)
            pass
        ```
        
        Dual limiting for OpenAI:
        ```python
        @choked(key="openai_chat", request_limit="50/s", token_limit="100000/m", token_estimator="openai")
        def chat_completion(messages):
            # Rate limited by both requests (50/s) and estimated tokens (100K/m)
            pass
        ```
    
    Raises:
        ValueError: If neither request_limit nor token_limit is provided, or if rate format is invalid.
    
    Note:
        - At least one of request_limit or token_limit must be provided
        - The decorator automatically detects if the wrapped function is async or sync
        - Both limits are enforced atomically - function only proceeds if both limits allow
        - Uses Redis for distributed rate limiting if CHOKED_API_TOKEN is not set
        - Uses proxy service for rate limiting if CHOKED_API_TOKEN environment variable is set
        - Token estimation requires appropriate packages (tiktoken, transformers)
    """
    def decorator(func: Callable) -> Callable:
        if request_limit is None and token_limit is None:
            raise ValueError("At least one of request_limit or token_limit must be provided")
        
        try:
            request_capacity, request_refill_rate = parse_rate_limit(request_limit)
            token_capacity, token_refill_rate = parse_rate_limit(token_limit)
        except ValueError as e:
            raise ValueError(f"Invalid rate limit format: {e}")
        
        bucket = get_token_bucket(key, request_capacity, request_refill_rate, token_capacity, token_refill_rate)
        estimator_func = ESTIMATORS.get(token_estimator if token_estimator else "default")
        
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            requests_needed = 1 if request_limit else 0
            tokens_needed = estimator_func(*args, **kwargs) if token_limit else 0
            
            current_sleep = 1.0
            while not await bucket.acquire(requests_needed, tokens_needed):
                jitter = random.uniform(0.8, 1.2)
                actual_sleep = current_sleep * jitter
                await asyncio.sleep(actual_sleep)
                current_sleep = current_sleep * 2
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            requests_needed = 1 if request_limit else 0
            tokens_needed = estimator_func(*args, **kwargs) if token_limit else 0

            current_sleep = 1.0
            while not asyncio.run(bucket.acquire(requests_needed, tokens_needed)):
                jitter = random.uniform(0.8, 1.2)
                actual_sleep = current_sleep * jitter
                time.sleep(actual_sleep)
                current_sleep = current_sleep * 2
            return func(*args, **kwargs)
        
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def get_token_bucket(key: str, request_capacity: int, request_refill_rate: float, token_capacity: int, token_refill_rate: float) -> Callable:
    """
    Factory function to create the appropriate dual rate limiting bucket implementation.
    
    This function determines whether to use a Redis-based dual bucket for local/distributed
    rate limiting or a proxy-based dual bucket for managed rate limiting service.
    
    Args:
        key (str): Unique identifier for the rate limit bucket.
        request_capacity (int): Maximum number of requests allowed (burst capacity).
        request_refill_rate (float): Requests refilled per second.
        token_capacity (int): Maximum number of tokens allowed (burst capacity).
        token_refill_rate (float): Tokens refilled per second.
    
    Returns:
        Callable: Either a RedisTokenBucket or ProxyTokenBucket instance depending on
            whether CHOKED_API_TOKEN environment variable is set.
    
    Environment Variables:
        CHOKED_API_TOKEN: If set, uses ProxyTokenBucket with this token for authentication.
            If not set, uses RedisTokenBucket for local Redis-based rate limiting.
    """
    token = os.getenv("CHOKED_API_TOKEN")
    if token:
        return ProxyTokenBucket(token, key, request_capacity, request_refill_rate, token_capacity, token_refill_rate)
    else:
        return RedisTokenBucket(key, request_capacity, request_refill_rate, token_capacity, token_refill_rate)