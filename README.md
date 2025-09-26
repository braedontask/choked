# 😵 Choked

**Simple, powerful Python rate limiting with dual limiting support.**

Choked is a class-based rate limiting library that uses the token bucket algorithm to control both request rates and token consumption. Perfect for AI/ML API integrations, multi-worker applications, and any scenario where you need intelligent dual rate limiting.

[![PyPI version](https://badge.fury.io/py/choked.svg)](https://badge.fury.io/py/choked)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **🎯 Simple**: Create an instance, use as decorator - no complex setup required
- **🤖 AI/ML Ready**: Built-in token estimation for OpenAI, VoyageAI, and general text
- **⚡ Dual Limiting**: Supports both request limits AND token limits simultaneously
- **🔄 Async/Sync**: Works seamlessly with both synchronous and asynchronous functions  
- **🌐 Distributed**: Share rate limits across processes and servers via Redis
- **📈 Scalable**: Perfect for multi-worker scenarios - auto-coordinates without manual tuning
- **🛡️ Reliable**: Battle-tested token bucket algorithm with atomic operations

## 🚀 Quick Start

### Installation

```bash
pip install choked
```

### Basic Usage

```python
from choked import Choked

# Create instance with Redis backend
choke = Choked(redis_url="redis://localhost:6379/0")

@choke(key="api_calls", request_limit="10/m")
def make_api_call():
    """This function can be called 10 times per minute"""
    return "API response"

# The decorator handles everything automatically
result = make_api_call()  # ✅ Works immediately
```

### AI/ML API Integration

```python
from choked import Choked
import openai

# Using managed proxy service for zero-infrastructure setup
choke = Choked(api_token="your-api-token")

@choke(key="openai_chat", request_limit="50/s", token_limit="100000/m", token_estimator="openai")
def chat_completion(messages):
    # Automatically estimates tokens from messages
    # Rate limited by both requests (50/s) AND tokens (100K/m)
    return openai.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

# Short message - limited by request rate
result = chat_completion([{"role": "user", "content": "Hi"}])

# Long message - may hit token limit first
long_msg = [{"role": "user", "content": "Very long message..." * 100}]
result = chat_completion(long_msg)
```

## 🎯 Perfect for Multi-Worker Applications

The real power of Choked shines when you have **multiple workers sharing the same API key**:

```python
from choked import Choked

# All workers automatically coordinate through Redis
choke = Choked(redis_url="redis://localhost:6379/0")

@choke(key="shared_openai", request_limit="100/s", token_limit="200000/m", token_estimator="openai")
def worker_api_call(messages):
    return openai.chat.completions.create(model="gpt-4", messages=messages)

# Scale from 1 to 100 workers - no configuration changes needed!
# ✅ Workers automatically share the 100 requests/s and 200K tokens/m
# ✅ No manual rate limit calculations
# ✅ No risk of exceeding API limits
```

## 📚 How It Works

Choked uses a **dual token bucket algorithm**:

1. 🪣 **Request bucket**: Tracks function calls (1 token per call)
2. 🧮 **Token bucket**: Tracks estimated tokens based on input text
3. ⏱️ Both buckets refill at steady rates (e.g., "100/s" = 100 tokens per second)
4. ⏳ Functions wait with smart exponential backoff when limits are reached

This allows **burst traffic** while respecting both **request** and **token limits** - exactly what you need for modern AI/ML APIs.

## ⚙️ Configuration

### Backend Options

Choose between Redis (self-hosted) or managed proxy service:

#### Redis Backend (Recommended for Production)
```python
from choked import Choked

choke = Choked(redis_url="redis://localhost:6379/0")
```

#### Managed Proxy Service (Zero Infrastructure)
```python
from choked import Choked

choke = Choked(api_token="your-api-token")
```

### Rate Limit Types

#### Request-Only Limiting
```python
@choke(key="simple_api", request_limit="100/s")
def api_call():
    return "Limited by requests only"
```

#### Token-Only Limiting (Perfect for Embeddings)
```python
@choke(key="embeddings", token_limit="1000000/m", token_estimator="voyageai")
def get_embeddings(texts):
    # Automatically estimates tokens from texts
    return voyage.embed(texts)
```

#### Dual Limiting (Best for Chat APIs)
```python
@choke(key="chat_api", request_limit="50/s", token_limit="100000/m", token_estimator="openai")
def chat_completion(messages):
    # Limited by both requests AND estimated tokens
    return openai.chat.completions.create(model="gpt-4", messages=messages)
```

## 🔧 Advanced Usage

### Multiple Services

```python
from choked import Choked

# Different instances for different services
openai_choke = Choked(api_token="openai-service-token")
voyage_choke = Choked(api_token="voyage-service-token")
redis_choke = Choked(redis_url="redis://localhost:6379/0")

@openai_choke(key="gpt4", request_limit="50/s", token_limit="100000/m", token_estimator="openai")
def gpt4_call(messages):
    return openai.chat.completions.create(model="gpt-4", messages=messages)

@voyage_choke(key="embed", token_limit="1000000/m", token_estimator="voyageai")
def voyage_embed(texts):
    return voyage.embed(texts)

@redis_choke(key="internal", request_limit="1000/s")
def internal_call():
    return "Internal API"
```

### Async Support

```python
import asyncio
from choked import Choked

choke = Choked(redis_url="redis://localhost:6379/0")

@choke(key="async_api", request_limit="10/s")
async def async_api_call(data):
    await asyncio.sleep(0.1)
    return f"Processed {data}"

async def main():
    result = await async_api_call("test")
    print(result)

asyncio.run(main())
```

### Shared Rate Limits

```python
from choked import Choked

choke = Choked(redis_url="redis://localhost:6379/0")

# Functions with the same key share rate limits
@choke(key="shared_resource", request_limit="10/m")
def function_a():
    return "A"

@choke(key="shared_resource", request_limit="10/m")
def function_b():
    return "B"

# Both functions compete for the same 10 requests/minute
```

## 🏗️ Real-World Examples

### OpenAI Integration

```python
import openai
from choked import Choked

choke = Choked(redis_url="redis://localhost:6379/0")

@choke(key="openai_gpt4", request_limit="50/s", token_limit="100000/m", token_estimator="openai")
def chat_with_gpt4(messages):
    return openai.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

@choke(key="openai_embed", token_limit="1000000/m", token_estimator="openai")
def get_embeddings(texts):
    return openai.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    )
```

### VoyageAI Integration

```python
import voyageai
from choked import Choked

choke = Choked(api_token="your-token")

@choke(key="voyage_embed", token_limit="1000000/m", token_estimator="voyageai")
def voyage_embeddings(texts, model="voyage-3"):
    return voyageai.embed(texts, model=model)
```

### Multi-Worker Web Scraping

```python
from choked import Choked
import requests

choke = Choked(redis_url="redis://localhost:6379/0")

@choke(key="scraper", request_limit="60/m")  # 1 request per second
def scrape_page(url):
    return requests.get(url).text

# Run this across multiple workers - they'll automatically coordinate
```

### FastAPI Integration

```python
from fastapi import FastAPI
from choked import Choked

app = FastAPI()
choke = Choked(redis_url="redis://localhost:6379/0")

@app.post("/chat")
@choke(key="api_chat", request_limit="100/s", token_limit="200000/m", token_estimator="openai")
async def chat_endpoint(messages: list[dict]):
    return openai.chat.completions.create(model="gpt-4", messages=messages)
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
pytest choked/test_choked.py 
pytest choked/token_bucket/test_token_bucket.py

# With Redis (requires Redis running)
export REDIS_URL="redis://localhost:6379/0"
pytest
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

- **AI/ML First**: Built specifically for token-based APIs like OpenAI, VoyageAI
- **Dual Limiting**: Respects both request rates and token consumption
- **Zero-config**: Works out of the box, scales when you need it
- **Developer-friendly**: Simple class-based interface, comprehensive docs
- **Production-ready**: Handles edge cases, network failures, and race conditions
- **Flexible**: Redis for DIY, managed service for convenience

---

**Ready to take control of your rate limits?** 

```bash
pip install choked
```

*Never exceed an API limit again.* 🚦