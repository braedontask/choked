import os
import time
import functools
import inspect
import asyncio
import random
import re

from typing import Any, Callable, Optional
from .token_bucket import RedisTokenBucket, ProxyTokenBucket

os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

import tiktoken
from transformers import AutoTokenizer


class Choked:
    """
    A configurable rate limiter that can use either Redis or a proxy service.
    
    This class provides a flexible interface for rate limiting that doesn't rely on
    environment variables. Users can specify either a Redis URL or API token directly.
    The class instance itself is callable as a decorator.
    
    Args:
        redis_url (str, optional): Redis connection URL for local/distributed rate limiting.
            Example: "redis://localhost:6379/0"
        api_token (str, optional): API token for managed rate limiting service.
        
    Note:
        Exactly one of redis_url or api_token must be provided.
        
    Examples:
        Using Redis:
        ```python
        choke = Choked(redis_url="redis://localhost:6379/0")
        
        @choke(key="api_calls", request_limit="10/s")
        def make_api_call():
            pass
        ```
        
        Using proxy service:
        ```python
        choke = Choked(api_token="your-api-token")
        
        @choke(key="openai_chat", request_limit="50/s", token_limit="100000/m", token_estimator="openai")
        def chat_completion(messages):
            pass
        ```
    """
    
    def __init__(self, redis_url: Optional[str] = None, api_token: Optional[str] = None):
        if redis_url and api_token:
            raise ValueError("Cannot specify both redis_url and api_token")
        if not redis_url and not api_token:
            raise ValueError("Must specify either redis_url or api_token")
            
        self.redis_url = redis_url
        self.api_token = api_token
        
        self.estimators = {
            'voyageai': self._voyageai_estimator,
            'openai': self._openai_estimator,
            'default': self._default_estimator,
        }
    
    def _parse_rate_limit(self, rate_str: Optional[str]) -> tuple[int, float]:
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

    def _extract_text_from_args(self, *args, **kwargs) -> list[str]:
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

    def _word_based_estimation(self, *args, **kwargs) -> int:
        """Fallback word-based token estimation (~0.75 tokens per word)."""
        texts = self._extract_text_from_args(*args, **kwargs)
        if not texts:
            return 1
        
        total_words = sum(len(text.split()) for text in texts)
        return max(1, int(total_words * 0.75))

    def _default_estimator(self, *args, **kwargs) -> int:
        """Default token estimator using tiktoken."""
        texts = self._extract_text_from_args(*args, **kwargs)
        if not texts:
            return 1
        
        try:
            encoding = tiktoken.encoding_for_model("gpt-4")
            total_tokens = sum(len(encoding.encode(text)) for text in texts)
            return total_tokens
        except Exception:
            return self._word_based_estimation(*args, **kwargs)

    def _voyageai_estimator(self, *args, **kwargs) -> int:
        """VoyageAI token estimator using HuggingFace tokenizer."""
        texts = self._extract_text_from_args(*args, **kwargs)
        if not texts:
            return 1
        
        try:
            tokenizer = AutoTokenizer.from_pretrained('voyageai/voyage-3.5')
            total_tokens = sum(len(tokenizer.encode(text)) for text in texts)
            return total_tokens
        except Exception:
            return self._default_estimator(*args, **kwargs)

    def _openai_estimator(self, *args, **kwargs) -> int:
        """OpenAI token estimator - uses default tiktoken estimator."""
        return self._default_estimator(*args, **kwargs)
    
    def _get_token_bucket(self, key: str, request_capacity: int, request_refill_rate: float, 
                         token_capacity: int, token_refill_rate: float) -> Callable:
        """Create the appropriate token bucket implementation."""
        if self.api_token:
            return ProxyTokenBucket(self.api_token, key, request_capacity, request_refill_rate, 
                                  token_capacity, token_refill_rate)
        else:
            return RedisTokenBucket(key, request_capacity, request_refill_rate, 
                                  token_capacity, token_refill_rate, redis_url=self.redis_url)
    
    def __call__(self, key: str, request_limit: Optional[str] = None, token_limit: Optional[str] = None, 
                token_estimator: Optional[str] = None) -> Callable:
        """
        Make the Choked instance callable as a decorator.
        
        This method allows the class instance to be used directly as a decorator with
        rate limiting parameters. It applies rate limiting to both synchronous and 
        asynchronous functions using the token bucket algorithm.
        
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
            choke = Choked(redis_url="redis://localhost:6379/0")
            
            @choke(key="api_calls", request_limit="10/s")
            def make_api_call():
                # This function is rate limited to 10 requests per second
                pass
            ```
            
            Token-only limiting for VoyageAI:
            ```python
            choke = Choked(api_token="your-token")
            
            @choke(key="voyage_embed", token_limit="1000000/m", token_estimator="voyageai")
            def get_embeddings(texts, model="voyage-3"):
                # Rate limited by estimated tokens (1M per minute)
                pass
            ```
            
            Dual limiting for OpenAI:
            ```python
            choke = Choked(redis_url="redis://localhost:6379/0")
            
            @choke(key="openai_chat", request_limit="50/s", token_limit="100000/m", token_estimator="openai")
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
            - Token estimation requires appropriate packages (tiktoken, transformers)
        """
        def decorator(func: Callable) -> Callable:
            if request_limit is None and token_limit is None:
                raise ValueError("At least one of request_limit or token_limit must be provided")
            
            try:
                request_capacity, request_refill_rate = self._parse_rate_limit(request_limit)
                token_capacity, token_refill_rate = self._parse_rate_limit(token_limit)
            except ValueError as e:
                raise ValueError(f"Invalid rate limit format: {e}")
            
            bucket = self._get_token_bucket(key, request_capacity, request_refill_rate, token_capacity, token_refill_rate)
            estimator_func = self.estimators.get(token_estimator if token_estimator else "default")
            
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

                # Re-use event loop for async Redis call. 
                loop = asyncio.get_event_loop()  
                while not loop.run_until_complete(bucket.acquire(requests_needed, tokens_needed)):
                    jitter = random.uniform(0.8, 1.2)
                    actual_sleep = current_sleep * jitter
                    time.sleep(actual_sleep)
                    current_sleep = current_sleep * 2
                return func(*args, **kwargs)
            
            return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
        
        return decorator
