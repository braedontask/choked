import requests

class ProxyTokenBucket:
    def __init__(self, token: str, key: str, max_tokens: int, refill_rate: float):
        self.token = token
        self.key = key
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.refill_period = int(max_tokens / refill_rate)
    
    async def acquire(self, tokens_needed: int = 1) -> bool:
        params = {
            "key": self.key,
            "max_tokens": self.max_tokens,
            "refill_period": self.refill_period,
            "tokens_needed": tokens_needed
        }
        
        response = requests.get(
            "https://api.try-marks.co/choked/acquire",
            params=params,
            headers={
                "Authorization": f"Bearer {self.token}"
            }
        )
        
        if response.status_code == 200:
            return True
        
        return False