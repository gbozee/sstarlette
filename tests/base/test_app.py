import asyncio

import httpx
import pytest


@pytest.mark.asyncio
async def test_service_route(client: httpx.AsyncClient):
    response = await client.get("/service", params={"name": "shola"})
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"name": "shola"}}


@pytest.mark.asyncio
async def test_default_route(client: httpx.AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"home": True}


@pytest.mark.asyncio
async def test_with_background(client: httpx.AsyncClient, mocker):
    mocked = mocker.patch("utils.mock_func")
    response = await client.get("/with-background")
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"result": "processing"}}
    mocked.assert_called_with(2)
    response = await client.get("/with-background", params={"keyword": True})
    mocked.assert_called_with(22, age=33)


@pytest.mark.asyncio
async def test_with_redirect(client: httpx.AsyncClient):
    response = await client.get("/with-redirect", allow_redirects=False)
    assert response.status_code == 301


@pytest.mark.asyncio
async def test_change_response_format(client):
    response = await client.get("with-error")
    assert response.status_code == 400
    assert response.json() == {"msg": "Bad info"}


@pytest.mark.asyncio
async def test_authenticated_route(client):
    response = await client.get(
        "/protected", headers={"Authorization": "Bearer Not Authorized 22"}
    )
    assert response.status_code == 400
    assert response.text == "Not Authorized"
    response = await client.get(
        "/protected", headers={"Authorization": "Bearer Allowed User"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": True,
        "data": {"name": "Shola", "roles": ["authenticated", "admin"]},
    }
