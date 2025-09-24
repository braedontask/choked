import os
import time
from dotenv import load_dotenv
import redis.asyncio as redis
from redis.exceptions import RedisError

load_dotenv()

TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local max_tokens = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])
local tokens_needed = tonumber(ARGV[4])

local last_refill = tonumber(redis.call('get', key .. ':last_refill') or now)
local current_tokens = tonumber(redis.call('get', key .. ':tokens') or max_tokens)

local time_passed = now - last_refill
local new_tokens = time_passed * refill_rate
current_tokens = math.min(max_tokens, current_tokens + new_tokens)

if current_tokens >= tokens_needed then
    current_tokens = current_tokens - tokens_needed
    redis.call('set', key .. ':tokens', current_tokens)
    redis.call('set', key .. ':last_refill', now)
    return 1
end

return 0
"""

class RedisTokenBucket:
    def __init__(self, key: str, max_tokens: int, refill_rate: float):
        self.redis = redis.Redis.from_url(os.getenv("REDIS_URL"))
        self.key = f"rate_limit:{key}"
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.script = self.redis.register_script(TOKEN_BUCKET_SCRIPT)

    async def acquire(self, tokens_needed: int = 1) -> bool:
        try:
            result = await self.script(
                keys=[self.key],
                args=[time.time(), self.max_tokens, self.refill_rate, tokens_needed]
            )
            return bool(result)
        except RedisError:
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.redis.aclose()
