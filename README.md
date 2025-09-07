# 😵 Choked

**Simple, powerful Python rate limiting that just works.**

Choked is a decorator-based rate limiting library that uses the token bucket algorithm to control function call rates. Perfect for API integrations, multi-worker applications, and any scenario where you need intelligent rate limiting.

[![PyPI version](https://badge.fury.io/py/choked.svg)](https://badge.fury.io/py/choked)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **🎯 Simple**: Just add a decorator - no complex setup required
- **⚡ Smart**: Exponential backoff with jitter prevents thundering herd
- **🔄 Async/Sync**: Works seamlessly with both synchronous and asynchronous functions  
- **🌐 Distributed**: Share rate limits across processes and servers via Redis
- **📈 Scalable**: Perfect for multi-worker scenarios - auto-coordinates without manual tuning
- **🛡️ Reliable**: Battle-tested token bucket algorithm with atomic operations

## 🚀 Quick Start

### Installation

```bash
pip install choked
```

### Sync + Async Usage

```python
from choked import choked

@choked(key="api_calls", max_tokens=10, refill_period=60)
def make_api_call():
    """This function can be called 10 times per minute"""
    return "API response"

# The decorator handles everything automatically
result = make_api_call()  # ✅ Works immediately
```

## 🎯 Perfect for Multi-Worker Applications

The real power of Choked shines when you have **multiple workers sharing the same API key**:

```python
# All workers automatically coordinate through Redis
@choked(key="shared_api_key", max_tokens=1000, refill_period=3600)  # 1000/hour
def worker_api_call():
    return make_external_api_call()

# Scale from 1 to 100 workers - no configuration changes needed!
# ✅ Workers automatically share the 1000 calls/hour
# ✅ No manual rate limit calculations
# ✅ No risk of exceeding API limits
```

## 📚 How It Works

Choked uses a **token bucket algorithm**:

1. 🪣 Each bucket starts with `max_tokens` 
2. ⏱️ Tokens refill at a steady rate (`max_tokens / refill_period` per second)
3. 🎫 Each function call consumes one token
4. ⏳ When empty, functions wait with smart exponential backoff

This allows **burst traffic** while maintaining **average rate limits** - exactly what you need for real-world applications.

## ⚙️ Configuration

### Redis Setup (Recommended)

For distributed rate limiting across multiple processes:

```bash
# Set your Redis connection
export REDIS_URL="redis://localhost:6379/0"
```

```python
from choked import choked

@choked(key="distributed_api", max_tokens=100, refill_period=3600)
def api_call():
    return "Shared across all processes!"
```

### Managed Service (Optional)

For zero-infrastructure rate limiting:

```bash
export CHOKED_API_TOKEN="your_token_here"
```

No Redis required - we handle the infrastructure for you.

## 🔧 Advanced Usage

### Shared Rate Limits

```python
# Multiple functions sharing the same bucket
@choked(key="shared_resource", max_tokens=10, refill_period=60)
def function_a():
    return "A"

@choked(key="shared_resource", max_tokens=10, refill_period=60) 
def function_b():
    return "B"

# Both functions compete for the same 10 calls/minute
```

## 🏗️ Real-World Examples

### Token-Based API Integration

```python
import openai
from choked import choked

# OpenAI has different limits for different models
@choked(key="openai_gpt4", max_tokens=500, refill_period=60)  # 500 requests/minute
def chat_with_gpt4(messages):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        max_tokens=150
    )
    return response.choices[0].message.content

# Multiple workers automatically coordinate token usage
```

### Multi-Worker Web Scraping

```python
from choked import choked
import requests

@choked(key="scraper", max_tokens=60, refill_period=60)  # 1 req/second
def scrape_page(url):
    return requests.get(url).text

# Run this across multiple workers - they'll automatically coordinate
```

### Database Operations

```python
@choked(key="db_heavy", max_tokens=10, refill_period=1)
async def heavy_database_operation():
    # Prevent overwhelming your database
    await run_expensive_query()
```

## 🛠️ Development

### Setup

```bash
git clone https://github.com/braedontask/choked.git
cd choked
pip install -e .
```

### Testing

```bash
# Run all tests
python -m pytest test_choked.py 
python -m pytest token_bucket/test_token_bucket.py

# With Redis (requires Redis running)
export REDIS_URL="redis://localhost:6379/0"
python -m pytest
```

### Contributing

We love contributions! Please feel free to:

- 🐛 Report bugs
- 💡 Suggest features  
- 📝 Improve documentation
- 🔧 Submit pull requests

## 📖 Documentation

For comprehensive guides and API documentation, visit our [documentation site](https://docs.choked.dev).

## 🤝 Support

- **Issues**: [GitHub Issues](https://github.com/braedontask/choked/issues)
- **Discussions**: [GitHub Discussions](https://github.com/braedontask/choked/discussions)
- **Twitter**: [@braedontask](https://x.com/braedontask)

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🌟 Why Choked?

- **Battle-tested**: Token bucket algorithm used by major platforms
- **Zero-config**: Works out of the box, scales when you need it
- **Developer-friendly**: Simple decorator interface, comprehensive docs
- **Production-ready**: Handles edge cases, network failures, and race conditions
- **Flexible**: Redis for DIY, managed service for convenience

---

**Ready to take control of your rate limits?** 

```bash
pip install choked
```

*Never exceed an API limit again.* 🚦