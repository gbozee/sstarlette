import httpx
import pytest


@pytest.mark.asyncio
async def test_send_email(client: httpx.AsyncClient, mocker):
    # missing template
    response = await client.post(
        "/send-email", json={"to": "john@example.com", "context": {"name": "Shola"},},
    )
    assert response.status_code == 400
    assert response.json() == {
        "status": False,
        "msg": "Missing template name in context",
    }
    # valid response
    mocked = mocker.patch("utils.bg_task")
    response = await client.post(
        "/send-email",
        json={
            "to": "john@example.com",
            "context": {"template_name": "danny.html", "name": "Shola"},
        },
    )
    assert response.status_code == 200
    mocked.assert_called_with(
        "john@example.com", "Hello Shola, This is a test template"
    )


@pytest.mark.asyncio
async def test_send_sms(client: httpx.AsyncClient, mocker):
    # when no phone number or message is sent
    response = await client.post("/send-sms", json={"to": "+2348123423234"})
    assert response.status_code == 400
    assert response.json() == {
        "status": False,
        "msg": "Missing recipient `to` or message `msg`",
    }
    # valid request
    mocked = mocker.patch("utils.bg_task")
    response = await client.post(
        "/send-sms", json={"to": "+2348123423234", "msg": "This is a test message"}
    )
    assert response.status_code == 200
    mocked.assert_called_with("+2348123423234", "This is a test message", "Main App")


@pytest.mark.asyncio
async def test_phone_verification(client: httpx.AsyncClient, mocker):
    # sending totp to phone

    response = await client.post(
        "/phone/send-verification", json={"number": "+2348123423234"}
    )
    assert response.status_code == 200
    mocked = mocker.patch("utils.bg_task")
    mocked.assert_called_with("+2348123423234")


@pytest.mark.asyncio
async def test_phone_confirmation(client: httpx.AsyncClient):
    response = await client.post(
        "/phone/confirm", json={"number": "+2348123423234", "code": "1234"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": {"msg": "Phone number verified"}}
