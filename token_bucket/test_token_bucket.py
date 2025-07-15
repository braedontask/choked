import uuid
import asyncio
import pytest
from redis_token_bucket import RedisTokenBucket

@pytest.mark.asyncio
async def test_token_bucket_limits_requests():
    async with RedisTokenBucket(f"tb-{uuid.uuid4()}", 3, 3 / 60) as bucket:
        assert await bucket.acquire() == True
        assert await bucket.acquire() == True
        assert await bucket.acquire() == True
        
        assert await bucket.acquire() == False
        assert await bucket.acquire() == False

@pytest.mark.asyncio
async def test_token_bucket_partial_refill():
    async with RedisTokenBucket(f"tb-refill-{uuid.uuid4()}", 1, 1 / 60) as bucket:
        assert await bucket.acquire() == True
        assert await bucket.acquire() == False
        
        await asyncio.sleep(1)
        
        assert await bucket.acquire() == False

@pytest.mark.asyncio
async def test_token_bucket_full_refill():
    async with RedisTokenBucket(f"tb-refill-{uuid.uuid4()}", 1, 1 / 5) as bucket:
        assert await bucket.acquire() == True
        assert await bucket.acquire() == False
        
        await asyncio.sleep(5)
        
        assert await bucket.acquire() == True
