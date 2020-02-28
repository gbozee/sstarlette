import asyncio
import typing

import httpx
import pytest

signup_data: typing.Dict[str, typing.Any] = {
    "full_name": "Fredo Alfredo",
    "email": "fredo@example.com",
}


@pytest.mark.asyncio
async def test_missing_signup_info(client: httpx.AsyncClient):
    # missing signup_info
    response = await client.post(
        "/signup", json={**signup_data, "password": "password101"}
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "msg": "Not Authorized"}


@pytest.mark.asyncio
async def test_provider_with_missing_auth(client: httpx.AsyncClient):
    # with provider but failed to pass authorization header
    response = await client.post(
        "/signup", json={**signup_data, "signup_info": {"provider": "custom"}}
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "msg": "Missing Auth header"}


@pytest.mark.asyncio
async def test_missing_password(client: httpx.AsyncClient):
    # missing form field
    response = await client.post(
        "/signup", json={**signup_data, "signup_info": {"verification": "email"}}
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "errors": {"password": "required"}}


# SUCCESS CASES
@pytest.mark.asyncio
async def test_provider_success(client: httpx.AsyncClient):
    # with provider
    response = await client.post(
        "/signup",
        json={**signup_data, "signup_info": {"provider": "custom"}},
        headers={"g_authorization": "Bearer Authorized Token"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": True,
        "data": {"access_token": "Success Access Token"},
    }


@pytest.mark.asyncio
async def test_password_success(client: httpx.AsyncClient, mocker):
    mocked = mocker.patch("utils.bg_task")
    # with password
    response = await client.post(
        "/signup",
        json={
            **signup_data,
            "signup_info": {"verification": "email"},
            "password": "password101",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": True,
        "data": {"access_token": "Success Access Token"},
    }
    mocked.assert_called_with("fredo@example.com")

