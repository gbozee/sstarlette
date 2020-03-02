import httpx
import pytest

headers = {"Authorization": "Bearer Authorized User"}


@pytest.mark.asyncio
async def test_send_email(auth_client: httpx.AsyncClient, mocker):
    # no authentication
    response = await auth_client.post(
        "/send-email",
        json={
            "to": "john@example.com",
            "context": {"template_name": "danny.html", "name": "Shola"},
        },
    )
    assert response.status_code == 403
    assert response.json() == {"status": False, "msg": "Not Authorized"}
    # valid response
    mocked = mocker.patch("utils.bg_task")
    response = await auth_client.post(
        "/send-email",
        json={
            "to": "john@example.com",
            "context": {"template_name": "danny.html", "name": "Shola"},
        },
        headers=headers,
    )
    assert response.status_code == 200
    mocked.assert_called_with(
        "john@example.com", "Hello Shola, This is a test template"
    )


@pytest.mark.asyncio
async def test_send_sms(auth_client: httpx.AsyncClient, mocker):
    # invalid authorization header
    response = await auth_client.post(
        "/send-sms",
        json={"to": "+2348123423234", "msg": "This is a test message"},
        headers={"Authorization": "Bearer Bad User"},
    )
    assert response.status_code == 403
    # valid request
    mocked = mocker.patch("utils.bg_task")
    response = await auth_client.post(
        "/send-sms",
        json={"to": "+2348123423234", "msg": "This is a test message"},
        headers=headers,
    )
    assert response.status_code == 200
    mocked.assert_called_with("+2348123423234", "This is a test message", "Main App")

