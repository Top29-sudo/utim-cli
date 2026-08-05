from slowapi import Limiter
from fastapi import Request

def get_user_rate_limit_key(request: Request) -> str:
    # 1. Try to get API key from headers to rate-limit by user
    x_api_key = request.headers.get("x-api-key")
    if x_api_key:
        return f"user:{x_api_key}"
        
    auth = request.headers.get("authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return f"user:{parts[1]}"
            
    # 2. Fall back to X-Forwarded-For IP if no API key is present
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
        
    return f"ip:{request.client.host}" if request.client else "ip:127.0.0.1"

limiter = Limiter(key_func=get_user_rate_limit_key)
