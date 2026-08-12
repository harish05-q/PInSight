import time

from jose import jwt, JWTError
import structlog
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.worker.queue import redis_conn

log = structlog.get_logger()
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify the JWT token and return the subject (client_id)."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token structure")
        return sub
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
) -> str | None:
    """Verify the JWT token and return client_id if present, else None."""
    if not credentials:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except Exception:
        return None


def rate_limit(request: Request, client_id: str | None = Depends(get_optional_user)):
    """Token bucket rate limiting using Redis."""
    # Settings for the bucket
    capacity = 100
    fill_rate = 10.0  # tokens per second

    # We use the client_id if authenticated, else IP address
    identifier = client_id if client_id else request.client.host
    key = f"rate_limit:{identifier}"

    now = time.time()

    # Run Lua script for atomic token bucket evaluation to avoid race conditions
    lua_script = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local fill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    
    local bucket = redis.call('HGETALL', key)
    local tokens = capacity
    local last_updated = now
    
    if #bucket > 0 then
        -- Convert hash array to dict
        local dict = {}
        for i = 1, #bucket, 2 do
            dict[bucket[i]] = bucket[i+1]
        end
        tokens = tonumber(dict['tokens'])
        last_updated = tonumber(dict['last_updated'])
    end
    
    local elapsed = math.max(0, now - last_updated)
    tokens = tokens + (elapsed * fill_rate)
    if tokens > capacity then
        tokens = capacity
    end
    
    if tokens >= 1 then
        tokens = tokens - 1
        redis.call('HMSET', key, 'tokens', tokens, 'last_updated', now)
        redis.call('EXPIRE', key, math.ceil(capacity / fill_rate) + 2)
        return 1
    else
        return 0
    end
    """

    try:
        allowed = redis_conn.eval(lua_script, 1, key, capacity, fill_rate, now)
        if not allowed:
            raise HTTPException(status_code=429, detail="Too Many Requests")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        # If Redis is down, we might want to log and allow, or reject. Let's allow gracefully.
        log.error("Rate limiter Redis error", error=str(e))
        pass
