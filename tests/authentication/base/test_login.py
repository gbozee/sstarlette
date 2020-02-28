import asyncio
import typing

import httpx
import pytest


@pytest.mark.asyncio
async def test_missing_password(client: httpx.AsyncClient):
    # email or password do not exist
    response = await client.post("/login", json={"email": "john@example.com"})
    assert response.json() == {"status": False, "msg": "Invalid credentials"}
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_provider_with_missing_header(client: httpx.AsyncClient):
    # provider with missing header
    response = await client.post(
        "/login",
        json={"email": "john@example.com", "login_info": {"provider": "custom"}},
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "msg": "Missing auth header"}


@pytest.mark.asyncio
async def test_provider_with_valid_header(client: httpx.AsyncClient):
    # provider with valid header
    response = await client.post(
        "/login",
        json={"email": "john@example.com", "login_info": {"provider": "custom"}},
        headers={"g_authorization": "Bearer Allowed access"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"access_token": "Access Token"}}


@pytest.mark.asyncio
async def test_valid_email_and_password(client: httpx.AsyncClient):
    # valid email and password
    response = await client.post(
        "/login", json={"email": "john@example.com", "password": "password"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"access_token": "Access Token"}}
