import uuid
import asyncio
import time
import pytest
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
