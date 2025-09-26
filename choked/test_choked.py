import uuid
import asyncio
import time
import pytest
from choked.choked import choked


@choked(f"tb-choked-{uuid.uuid4()}", request_limit="3/s")
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
    
    min_expected_duration = 2
    assert total_duration >= min_expected_duration, f"Test completed too quickly: {total_duration:.2f}s < {min_expected_duration}s"
    
    max_expected_duration = 5
    assert total_duration <= max_expected_duration, f"Test took too long: {total_duration:.2f}s > {max_expected_duration}s"


@pytest.mark.asyncio
async def test_voyageai_token_estimation():
    """Test VoyageAI token estimation with rate limiting using real tokenizer."""
    @choked(
        key=f"voyage-test-{uuid.uuid4()}", 
        token_limit="50/s",
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
    
    assert total_duration >= 1.0, f"Test completed too quickly: {total_duration:.2f}s - rate limiting should have occurred"
    assert total_duration <= 4.0, f"Test took too long: {total_duration:.2f}s"


@pytest.mark.asyncio
async def test_dual_rate_limiting_decorator():
    """Test that the decorator enforces both request and token limits simultaneously."""
    
    @choked(
        key=f"dual-test-{uuid.uuid4()}", 
        request_limit="5/s",  
        token_limit="150/s",   
    )
    async def dual_limited_function(text: str = "short"):
        return f"processed: {text}"
    
    request_test_start_time = time.time()

    tasks = [
        dual_limited_function("hi") for _ in range(11)
    ]

    _ = await asyncio.gather(*tasks)

    request_test_end_time = time.time()

    request_test_total_time = request_test_end_time - request_test_start_time
    
    assert request_test_total_time >= 1.2, f"Request test completed too quickly: {request_test_total_time:.2f}s"
    assert request_test_total_time <= 3.0, f"Request test took too long: {request_test_total_time:.2f}s"

    await asyncio.sleep(5)

    long_text = "This is a very long piece of text that contains many words and should consume significantly more than twenty tokens when processed by the tiktoken tokenizer, which will cause the token-based rate limiting to kick in and delay the function execution. The text continues with more words to ensure we exceed the token budget and trigger rate limiting behavior."

    token_test_start_time = time.time()

    tasks = [
        dual_limited_function(long_text) for _ in range(5)
    ]

    _ = await asyncio.gather(*tasks)

    token_test_end_time = time.time()

    token_test_total_time = token_test_end_time - token_test_start_time

    print(f"Token test took: {token_test_total_time:.2f}s")

    assert token_test_total_time >= 2.0, f"Token test completed too quickly: {token_test_total_time:.2f}s"
    assert token_test_total_time <= 4.0, f"Token test took too long: {token_test_total_time:.2f}s"


def test_validation_errors():
    """Test that proper validation errors are raised during decorator creation."""
    
    with pytest.raises(ValueError, match="At least one of request_limit or token_limit must be provided"):
        @choked(key="test")
        def no_limits_function():
            return "fail"
    
    with pytest.raises(ValueError, match="Invalid rate limit format"):
        @choked(key="test", request_limit="invalid")
        def invalid_format_function():
            return "fail"


def test_rate_parsing():
    """Test the rate parsing function."""
    from choked.choked import parse_rate_limit
    
    assert parse_rate_limit("100/s") == (100, 100.0)
    assert parse_rate_limit("6000/m") == (6000, 100.0)
    assert parse_rate_limit("1/s") == (1, 1.0)
    assert parse_rate_limit("60/m") == (60, 1.0)
    
    assert parse_rate_limit(None) == (0, 0.0)
    
    with pytest.raises(ValueError, match="Invalid rate format"):
        parse_rate_limit("invalid")
    
    with pytest.raises(ValueError, match="Invalid rate format"):
        parse_rate_limit("100/h")
    
    with pytest.raises(ValueError, match="Invalid rate format"):
        parse_rate_limit("100")

    with pytest.raises(ValueError, match="Invalid rate format"):
        parse_rate_limit("/s")
