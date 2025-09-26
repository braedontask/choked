import os
import time
from dotenv import load_dotenv
import redis.asyncio as redis
from redis.exceptions import RedisError

load_dotenv()

DUAL_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])

-- Evaluate request limit

local max_requests = tonumber(ARGV[2])
local request_refill_rate = tonumber(ARGV[3])
local requests_needed = tonumber(ARGV[4])

local request_last_refill = tonumber(redis.call('get', key .. ':request_last_refill') or now)
local current_requests = tonumber(redis.call('get', key .. ':requests') or max_requests)
local request_time_passed = now - request_last_refill
local new_requests = request_time_passed * request_refill_rate
current_requests = math.min(max_requests, current_requests + new_requests)
local request_limit_ok = current_requests >= requests_needed

-- Evaluate token limit

local max_tokens = tonumber(ARGV[5])
local token_refill_rate = tonumber(ARGV[6])
local tokens_needed = tonumber(ARGV[7])

local token_last_refill = tonumber(redis.call('get', key .. ':token_last_refill') or now)
local current_tokens = tonumber(redis.call('get', key .. ':tokens') or max_tokens)
local token_time_passed = now - token_last_refill
local new_tokens = token_time_passed * token_refill_rate
current_tokens = math.min(max_tokens, current_tokens + new_tokens)
local token_limit_ok = current_tokens >= tokens_needed

-- Final result: both limits must be satisfied

if request_limit_ok and token_limit_ok then

    -- Consume from both limits

    current_requests = current_requests - requests_needed
    current_tokens = current_tokens - tokens_needed
    
    -- Update both limits

    redis.call('set', key .. ':requests', current_requests)
    redis.call('set', key .. ':request_last_refill', now)
    redis.call('set', key .. ':tokens', current_tokens)
    redis.call('set', key .. ':token_last_refill', now)
    
    return 1
end

return 0
"""

class RedisTokenBucket:
    def __init__(self, key: str, request_capacity: int, request_refill_rate: float, token_capacity: int, token_refill_rate: float):
        self.redis = redis.Redis.from_url(os.getenv("REDIS_URL"))
        self.key = f"rate_limit:{key}"
        self.request_capacity = request_capacity
        self.token_capacity = token_capacity
        self.request_refill_rate = request_refill_rate
        self.token_refill_rate = token_refill_rate
        self.script = self.redis.register_script(DUAL_RATE_LIMIT_SCRIPT)

    async def acquire(self, requests_needed: int = 1, tokens_needed: int = 0) -> bool:
        try:
            result = await self.script(
                keys=[self.key],
                args=[
                    time.time(),
                    self.request_capacity,
                    self.request_refill_rate,
                    requests_needed,
                    self.token_capacity,
                    self.token_refill_rate,
                    tokens_needed
                ]
            )
            return bool(result)
        except RedisError:
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.redis.aclose()
