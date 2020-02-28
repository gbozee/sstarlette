import asyncio
import typing

import httpx
import pytest


@pytest.mark.asyncio
async def test_forgot_password(client: httpx.AsyncClient, mocker):
    email_notification_func = mocker.patch("utils.bg_task")
    response = await client.get(
        "/forgot-password",
        params={"email": "fredo@example.com", "callback_url": "http://google.com"},
    )
    email_notification_func.assert_called_once_with(
        "fredo@example.com", callback_url="http://google.com"
    )
    assert response.status_code == 200
    assert response.json() == {"status": True}


@pytest.mark.asyncio
async def test_reset_password(client: httpx.AsyncClient):
    # when no authentication header is passed
    response = await client.post("/reset-password", json={"password": "password"})
    assert response.status_code == 403
    assert response.json() == {"status": False, "msg": "Not Authorized"}

    # when valid authentication header is passed
    response = await client.post(
        "/reset-password",
        json={"password": "password"},
        headers={"Authorization": "Bearer Valid Header"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": True}


@pytest.mark.asyncio
async def test_get_profile(client: httpx.AsyncClient):
    # when no authenticated header is passed
    response = await client.get("/get-profile")
    assert response.status_code == 403
    assert response.json() == {"status": False, "msg": "Not Authorized"}
    # when user is fetching the profile
    response = await client.get(
        "/get-profile", headers={"Authorization": "Bearer Valid Header"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"email": "james@example.com"}}
    # when user tries to access another profile and is not staff or admin
    response = await client.get(
        "/get-profile",
        params={"email": "shola@example.com"},
        headers={"Authorization": "Bearer Valid Header"},
    )
    assert response.status_code == 403
    assert response.json() == {"status": False, "msg": "Not Authorized"}
    # when staff or admin is fetching the profile
    response = await client.get(
        "/get-profile",
        params={"email": "shola@example.com"},
        headers={"Authorization": "Bearer Staff Header"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"email": "shola@example.com"}}


@pytest.mark.asyncio
async def test_delete_user(client: httpx.AsyncClient):
    # when regular user tries to delete user
    response = await client.delete(
        "/delete-user",
        params={"email": "shola@example.com"},
        headers={"Authorization": "Bearer Valid Header"},
    )
    assert response.status_code == 403
    assert response.json() == {"status": False, "msg": "Not Authorized"}
    # when user does not exist
    response = await client.delete(
        "/delete-user",
        params={"email": "john@example.com"},
        headers={"Authorization": "Bearer Staff Header"},
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "msg": "Missing email"}
    # Authorized staff valid
    response = await client.delete(
        "/delete-user",
        params={"email": "shola@example.com"},
        headers={"Authorization": "Bearer Staff Header"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"msg": "Done"}}


@pytest.mark.asyncio
async def test_hijack_user(client: httpx.AsyncClient):
    # when regular user tries to delete user
    response = await client.get(
        "/hijack-user",
        params={"email": "shola@example.com"},
        headers={"Authorization": "Bearer Valid Header"},
    )
    assert response.status_code == 403
    assert response.json() == {"status": False, "msg": "Not Authorized"}
    # when email is missing
    response = await client.get(
        "/hijack-user", headers={"Authorization": "Bearer Staff Header"}
    )
    assert response.status_code == 400
    assert response.json() == {"status": False, "msg": "Missing email"}

    # when user does not exist
    response = await client.get(
        "/hijack-user",
        params={"email": "john@example.com"},
        headers={"Authorization": "Bearer Staff Header"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "status": False,
        "msg": f"No user with email <john@example.com>",
    }
    # Authorized staff valid
    response = await client.get(
        "/hijack-user",
        params={"email": "shola@example.com"},
        headers={"Authorization": "Bearer Staff Header"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": True,
        "data": {"access_token": "Hijacked token"},
    }

