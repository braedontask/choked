import uuid
import asyncio
import time
import pytest
from unittest.mock import patch, MagicMock
from choked.choked import choked

@choked(f"tb-choked-{uuid.uuid4()}", 3, 3, sleep_time=0.1)
async def rate_limited_function():
    return True

async def worker(id: int, results: list[dict], start_time: float):
    worker_start = time.time()
    result = await rate_limited_function()
    worker_end = time.time()
    results.append({
        'id': id,
        'success': result,
        'start_time': worker_start - start_time,
        'end_time': worker_end - start_time,
        'duration': worker_end - worker_start
    })

@pytest.mark.asyncio
async def test_concurrent_rate_limiting():
    num_workers = 8
    results: list[dict] = []
    start_time = time.time()
    
    workers = [
        worker(i, results, start_time)
        for i in range(num_workers)
    ]
    
    await asyncio.gather(*workers)
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    assert len(results) == num_workers, f"Expected {num_workers} results, got {len(results)}"
    
    successful_requests = [r for r in results if r['success']]
    assert len(successful_requests) == num_workers, f"Expected {num_workers} successful requests, got {len(successful_requests)}"
    
    min_expected_duration = 4
    assert total_duration >= min_expected_duration, f"Test completed too quickly: {total_duration:.2f}s < {min_expected_duration}s"
    
    max_expected_duration = 10
    assert total_duration <= max_expected_duration, f"Test took too long: {total_duration:.2f}s > {max_expected_duration}s"


@pytest.mark.asyncio
async def test_voyageai_token_estimation():
    """Test VoyageAI token estimation with rate limiting using real tokenizer."""
    @choked(
        key=f"voyage-test-{uuid.uuid4()}", 
        max_tokens=50, 
        refill_period=2, 
        sleep_time=0.1,
        token_estimator="voyageai"
    )
    async def mock_voyage_embed(texts, model="voyage-3"):
        await asyncio.sleep(0.01)
        return {"embeddings": [[0.1, 0.2] for _ in texts]}
    
    start_time = time.time()
    
    result1 = await mock_voyage_embed(texts=["Hello"], model="voyage-3")
    assert result1 == {"embeddings": [[0.1, 0.2]]}
    
    long_text = "This is a much longer piece of text that contains many words and should consume significantly more tokens when processed by the VoyageAI tokenizer, potentially causing rate limiting to kick in."
    result2 = await mock_voyage_embed(texts=[long_text], model="voyage-3")
    assert result2 == {"embeddings": [[0.1, 0.2]]}
    
    result3 = await mock_voyage_embed(texts=[long_text], model="voyage-3")
    assert result3 == {"embeddings": [[0.1, 0.2]]}
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Funny time-based tests that do the trick for now... These should be replaced with mocks checking rate limit response.
    assert total_duration >= 1.0, f"Test completed too quickly: {total_duration:.2f}s - rate limiting should have occurred"
    assert total_duration <= 10.0, f"Test took too long: {total_duration:.2f}s"
