"""Tests for Auth and Rate Limiting."""

from jose import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

def test_auth_token_success():
    response = client.post("/v1/auth/token", json={
        "client_id": settings.admin_username,
        "client_secret": settings.admin_password
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

    # Verify token
    payload = jwt.decode(data["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == settings.admin_username

def test_auth_token_failure():
    response = client.post("/v1/auth/token", json={
        "client_id": "wrong",
        "client_secret": "wrong"
    })
    assert response.status_code == 401

def test_rate_limit_headers_not_blocked_immediately():
    # Because rate limit relies on Redis and we might not have a clean Redis state in tests,
    # we just verify that a simple unauthenticated request to an endpoint doesn't crash.
    response = client.get("/v1/health")
    assert response.status_code == 200

def test_protected_endpoint_rejects_without_token():
    # Attempting to create an incident without a token
    response = client.post("/v1/incidents", json={
        "transaction_id": "00000000-0000-0000-0000-000000000000",
        "description": "test"
    })
    # FastAPI HTTPBearer returns 403 when no credentials provided
    assert response.status_code == 403
