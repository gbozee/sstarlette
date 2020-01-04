import os
from datetime import datetime

import httpx
import jwt
import pytest
from starlette import testclient

from authentication_service import models, settings
from authentication_service.models.utils import decode_access_token as decode_token
from shared import clear_db, create_roles_and_permissions, create_user


async def login_helper(json_params: dict, headers: dict = None):
    response = client.post(
        "/login", json={"email": "fredo@example.com", **json_params}, headers=headers
    )
    return response


@pytest.fixture
def mock_generate_token(mocker):
    def _mocker(result="access token"):
        _mock_generate_token = mocker.patch(
            "sstarlette.authentication.models.token_encoder_and_decoder"
        )
        # mock_generate_token = mocker.patch(
        #     "authentication_service.models.create_access_token"
        # )
        _mock_generate_token.return_value = (
            lambda *args, **kwargs: result,
            lambda *args, **kwargs: "",
        )
        return _mock_generate_token

    return _mocker


@pytest.mark.run_loop
async def test_reset_user_password(
    client: httpx.Client, mocker, create_redis, create_future
):
    async with models.User.database:
        await clear_db()
        user: models.User = await create_user()
        assert not user.password
        # when no token is passed expect 403 response
        response = await client.post("/reset-password", json={"password": "password"})
        assert response.status_code == 403
        assert response.json() == {"status": False, "msg": "Not Authorized"}
        # # when token has expired
        mock_now = mocker.patch("sstarlette.authentication.helpers.current_time")
        mock_now.return_value = datetime(2019, 8, 15, 5, 4, 3)
        token = await user.generate_access_token(expires=60 * 60)
        mock_now.return_value = datetime.now()
        response = await client.post(
            "/reset-password",
            json={"password": "password"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert response.json() == {
            "status": False,
            "msg": "Token is invalid or expired",
        }
        # valid use case
        token = await user.generate_access_token()
        response = await client.post(
            "/reset-password",
            json={"password": "password"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": True}
        user = await models.User.objects.first()
        assert user.check_password("password")


@pytest.mark.run_loop
async def test_forgot_user_password(
    client: testclient.TestClient, mocker, create_future
):
    email_notification_func = mocker.patch(
        "authentication_service.views.email_verification"
    )
    email_notification_func.return_value = create_future({})
    async with models.User.database:
        await clear_db()
        await create_user()
        response = await client.get(
            "/forgot-password",
            params={"email": "fredo@example.com", "callback_url": "http://google.com"},
        )
        email_notification_func.assert_called_once_with(
            "fredo@example.com", callback_url="http://google.com"
        )
        assert response.status_code == 200
        assert response.json() == {"status": True, "data": None}


@pytest.mark.run_loop
async def test_verify_email_confirmation(
    client: httpx.Client, mocker, create_future, create_redis, mock_generate_token
):
    async with models.User.database:
        await clear_db()
        user: models.User = await create_user()
        token = await user.generate_access_token(expires=15 * 60)
        # when the user just signed up and needs to verify email.
        assert not user.email_verified
        response = await client.get(
            "/verify-email",
            params={"email": "fredo@example.com", "token": token},
            # allow_redirects=False,
        )
        assert response.status_code == 200
        assert response.url == settings.REDIRECT_URL_ON_EMAIL_VERIFICATION
        user = await models.User.objects.first()
        assert user.email_verified
        # when the user forgot password. in this case, a callback_url is required
        mock_token = mock_generate_token("user_token")
        response = await client.get(
            "/verify-email",
            params={
                "email": "fredo@example.com",
                "token": token,
                "callback_url": "http://testserver.com",
            },
        )
        assert response.status_code == 200
        assert response.url == f"http://testserver.com?access_token=user_token"


def reset_token_helper(json_params: dict = {}):
    response = client.get(
        "/refresh-token",
        params={
            "token": "GeneratedToken",
            "callback_url": "http://google.com",
            **json_params,
        },
    )
    return response


@pytest.mark.run_loop
async def test_login_with_email_and_password(
    client: testclient.TestClient, mocker, create_future
):
    async with models.User.database:
        await clear_db()
        # regular user login
        await create_roles_and_permissions()
        regular_user = await create_user(password="password")
        staff_user = await create_user(
            "Staff", password="password", email="staff@example.com"
        )
        response = await client.post(
            "/login", json={"email": "fredo@example.com", "password": "password"}
        )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        d_token = decode_token(token)
        assert "fredo@example.com" in d_token.values()
        # regular staff login . treat staff as agent
        response = await client.post(
            "/login",
            json={"email": "staff@example.com", "password": "password"},
            headers={"StaffAuth": "Bearer StaffAccess"},
        )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        d_token = jwt.decode(token, verify=False)
        assert "aud" in d_token
        # staff login as regular user
        response = await client.post(
            "/login", json={"email": "staff@example.com", "password": "password"}
        )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        d_token = jwt.decode(token, verify=False)
        assert "aud" not in d_token
        # with phone number instead of email
        # when phone doesn't match email
        mock_auth = mocker.patch(
            "authentication_service.service_layer.utils.get_email_from_number"
        )
        mock_auth.return_value = create_future("johndoe@example.com")
        response = await client.post(
            "/login",
            json={
                "number": "+2347035409922",
                "password": "password",
                "login_info": {"endpoint": "http://client.example.com"},
            },
        )
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Invalid credentials"}
        # when phone number matches
        mock_auth.return_value = create_future("fredo@example.com")
        response = await client.post(
            "/login",
            json={
                "number": "+2347035409922",
                "password": "password",
                "login_info": {"endpoint": "http://client.example.com"},
            },
        )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        d_token = jwt.decode(token, verify=False)
        assert "fredo@example.com" in d_token.values()
        # assert response.json() == {
        #     "status": True,
        #     "data": {"access_token": "Generated Token"},
        # }


@pytest.mark.run_loop
async def test_provider_login(
    client: testclient.TestClient, mocker, create_future, mock_generate_token
):
    mock_generate_token()
    provider_authorization = mocker.patch(
        "authentication_service.service_layer.utils.provider_verification"
    )
    async with models.User.database:
        await clear_db()
        regular_user = await create_user()
        # missing auth header
        response = await client.post(
            "/login",
            json={
                "email": "fredo@example.com",
                "login_info": {"provider": "google", "client_id": "google_client_id"},
            },
        )
        assert response.status_code == 400
        assert response.json() == {
            "status": False,
            "msg": "Missing Authorization header",
        }
        # failed identity verification
        provider_authorization.return_value = create_future(False)
        response = await client.post(
            "/login",
            json={
                "email": "fredo@example.com",
                "login_info": {"provider": "google", "client_id": "google_client_id"},
            },
            headers={"G_Authorization": "Bearer GoogleToken"},
        )
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Error verifying identity"}
        # successful identity verification
        provider_authorization.return_value = create_future(True)
        response = await client.post(
            "/login",
            json={
                "email": "fredo@example.com",
                "login_info": {"provider": "google", "client_id": "google_client_id"},
            },
            headers={"G_Authorization": "Bearer GoogleToken"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": True,
            "data": {"access_token": "access token"},
        }


@pytest.mark.run_loop
async def test_passwordless_login_by_email(
    client: testclient.TestClient, mocker, create_future, mock_generate_token
):
    email_notification_func = mocker.patch(
        "authentication_service.service_layer.utils.email_verification"
    )
    mock_generate_token()
    async with models.User.database:
        await clear_db()
        regular_user = await create_user()
        response = await client.post(
            "/login",
            json={"email": "fredo@example.com", "callback_url": "http://google.com"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": True,
            "data": {"msg": "Email verification sent"},
        }
        email_notification_func.assert_called_once_with(
            "fredo@example.com", token="access token", callback_url="http://google.com"
        )


@pytest.mark.run_loop
async def test_hijack_user(
    client: testclient.TestClient, mocker, create_future, create_redis
):
    async with models.User.database:
        await clear_db()
        await create_roles_and_permissions()
        regular_user = await create_user(password="password")
        staff_user: models.User = await create_user(
            "Staff", password="password", email="staff@example.com"
        )
        # user token attempt
        staff_token = await staff_user.create_user_token()
        response = await client.get(
            "/hijack-user",
            params={"email": "fredo@example.com"},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert response.status_code == 403
        assert response.json() == {"status": False, "msg": "Not Authorized"}
        # valid staff token
        staff_token = await staff_user.generate_access_token()
        response = await client.get(
            "/hijack-user",
            params={"email": "fredo@example.com"},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        result = jwt.decode(token, verify=False)
        assert "fredo@example.com" in result.values()
        assert "hijacker" in result.keys()
        assert "staff@example.com" in result.values()


@pytest.mark.run_loop
async def test_get_auth_info(client: testclient.TestClient):
    pass
