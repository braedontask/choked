import os
import uuid
import asyncio
import pytest
from dotenv import load_dotenv
from choked import RedisTokenBucket

load_dotenv()


@pytest.mark.asyncio
async def test_token_bucket_limits_requests():
    async with RedisTokenBucket(f"tb-{uuid.uuid4()}", request_capacity=3, request_refill_rate=1.0, token_capacity=0, token_refill_rate=0.0, redis_url=os.getenv("REDIS_URL")) as bucket:
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True
        
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == False
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == False


@pytest.mark.asyncio
async def test_token_bucket_partial_refill():
    async with RedisTokenBucket(f"tb-refill-{uuid.uuid4()}", request_capacity=1, request_refill_rate=1.0, token_capacity=0, token_refill_rate=0.0, redis_url=os.getenv("REDIS_URL")) as bucket:
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == False
        
        await asyncio.sleep(1)
        
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True


@pytest.mark.asyncio
async def test_token_bucket_full_refill():
    async with RedisTokenBucket(f"tb-refill-{uuid.uuid4()}", request_capacity=5, request_refill_rate=1.0, token_capacity=0, token_refill_rate=0.0, redis_url=os.getenv("REDIS_URL")) as bucket:
        for _ in range(5):
            assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True
        
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == False
        
        await asyncio.sleep(5)
        
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True


@pytest.mark.asyncio
async def test_dual_rate_limiting():
    """Test that both request and token limits are enforced."""
    async with RedisTokenBucket(f"tb-dual-{uuid.uuid4()}", request_capacity=5, request_refill_rate=1.0, token_capacity=10, token_refill_rate=1.0, redis_url=os.getenv("REDIS_URL")) as bucket:
        assert await bucket.acquire(requests_needed=1, tokens_needed=5) == True
        assert await bucket.acquire(requests_needed=1, tokens_needed=5) == True
        
        # We do not consume tokens or requests here due to the failure!
        assert await bucket.acquire(requests_needed=1, tokens_needed=1) == False
        
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True

        # Consequently, we do have the bandwidth for the 5th request!
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == True
        
        assert await bucket.acquire(requests_needed=1, tokens_needed=0) == False
