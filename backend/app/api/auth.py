import time
from typing import Any

from jose import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/token", response_model=TokenResponse)
async def issue_token(req: TokenRequest) -> dict[str, Any]:
    """Issue a JWT token for the admin client."""
    if req.client_id != settings.admin_username or req.client_secret != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    now = int(time.time())
    expires_in = settings.jwt_expire_minutes * 60

    payload = {"sub": req.client_id, "iat": now, "exp": now + expires_in, "role": "admin"}

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}
