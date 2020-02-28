import asyncio
import typing

import httpx
import pytest


@pytest.mark.asyncio
async def test_missing_email_or_token(client: httpx.AsyncClient):
    # when email or token is missing
    response = await client.get(
        "/verify-email",
        params={"token": "InvValid Token"},
        # allow_redirects=False,
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "msg": "Missing query parameters"}


@pytest.mark.asyncio
async def test_invalid_token(client: httpx.AsyncClient):
    # when token is invalid
    response = await client.get(
        "/verify-email",
        params={"email": "fredo@example.com", "token": "InValid Token"},
        # allow_redirects=False,
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "msg": "Invalid token"}


@pytest.mark.asyncio
async def test_fallback_callback(client: httpx.AsyncClient):
    # when callback_url is not specified
    response = await client.get(
        "/verify-email",
        params={"email": "fredo@example.com", "token": "Valid Token"},
        # allow_redirects=False,
    )
    assert response.url == f"http://google.com?access_token=user_token"


@pytest.mark.asyncio
async def test_specified_callback(client: httpx.AsyncClient):
    # when callback_url is specified
    response = await client.get(
        "/verify-email",
        params={
            "email": "fredo@example.com",
            "token": "Valid Token",
            "callback_url": "http://testserver.com",
        },
    )
    assert response.url == f"http://testserver.com?access_token=user_token"

