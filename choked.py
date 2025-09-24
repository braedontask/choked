import os
import time
import functools
import inspect
import asyncio
import random
from dotenv import load_dotenv
from typing import Any, Callable, Optional
import tiktoken
from transformers import AutoTokenizer
from .token_bucket.redis_token_bucket import RedisTokenBucket
from .token_bucket.proxy_token_bucket import ProxyTokenBucket

load_dotenv()

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


def choked(key: str, max_tokens: int, refill_period: int, sleep_time: float = 1.0, token_estimator: Optional[str] = None) -> Callable:
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
        token_estimator (str, optional): Token estimation method. Options:
            - None: Request-based limiting (1 token per call)
            - 'voyageai': Use VoyageAI tokenizer for text estimation
            - 'openai': Use OpenAI/tiktoken for text estimation
            - 'default'/'tiktoken': Use tiktoken with GPT-4 tokenizer
    
    Returns:
        Callable: A decorator function that can be applied to sync or async functions.
    
    Examples:
        Basic usage (request-based):
        ```python
        @choked(key="api_calls", max_tokens=10, refill_period=60)
        def make_api_call():
            # This function is rate limited to 10 calls per minute
            pass
        ```
        
        Token-based limiting for VoyageAI:
        ```python
        @choked(key="voyage_embed", max_tokens=1000000, refill_period=3600, token_estimator="voyageai")
        def get_embeddings(texts, model="voyage-3"):
            # Rate limited by estimated token consumption
            pass
        ```
        
        Token-based limiting for OpenAI:
        ```python
        @choked(key="openai_chat", max_tokens=100000, refill_period=3600, token_estimator="openai")
        def chat_completion(messages):
            # Rate limited by estimated token consumption
            pass
        ```
    
    Note:
        - The decorator automatically detects if the wrapped function is async or sync
        - Uses Redis for distributed rate limiting if CHOKED_API_TOKEN is not set
        - Uses proxy service for rate limiting if CHOKED_API_TOKEN environment variable is set
        - Sleep time increases exponentially (doubles) on each retry with random jitter (0.8x to 1.2x)
        - Token estimation requires appropriate packages (tiktoken, transformers)
    """
    def decorator(func: Callable) -> Callable:
        bucket = get_token_bucket(key, max_tokens, refill_period)
        estimator_func = ESTIMATORS.get(token_estimator) if token_estimator else None
        
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tokens_needed = estimator_func(*args, **kwargs) if estimator_func else 1
            
            current_sleep = sleep_time
            while not await bucket.acquire(tokens_needed):
                jitter = random.uniform(0.8, 1.2)
                actual_sleep = current_sleep * jitter
                await asyncio.sleep(actual_sleep)
                current_sleep = current_sleep * 2
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tokens_needed = estimator_func(*args, **kwargs) if estimator_func else 1
            
            current_sleep = sleep_time
            while not asyncio.run(bucket.acquire(tokens_needed)):
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