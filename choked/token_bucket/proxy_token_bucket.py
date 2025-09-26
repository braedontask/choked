import requests

class ProxyTokenBucket:
    def __init__(self, token: str, key: str, request_capacity: int, request_refill_rate: float, token_capacity: int, token_refill_rate: float):
        self.token = token
        self.key = key
        self.request_capacity = request_capacity
        self.request_refill_rate = request_refill_rate
        self.token_capacity = token_capacity
        self.token_refill_rate = token_refill_rate
    
    async def acquire(self, requests_needed: int = 1, tokens_needed: int = 0) -> bool:
        params = {
            "key": self.key,
            "request_capacity": self.request_capacity,
            "request_refill_rate": self.request_refill_rate,
            "token_capacity": self.token_capacity,
            "token_refill_rate": self.token_refill_rate,
            "requests_needed": requests_needed,
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