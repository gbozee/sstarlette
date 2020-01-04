import unittest

import httpx
import pytest
from starlette import testclient

from authentication_service import models
from tests.views.shared import db_assertion, user_email_verification_assertion


async def user_count_assertion(user_count):
    assert await models.User.objects.count() == 0


@pytest.fixture
def mock_generate_token(mocker):
    _mock_generate_token = mocker.patch(
        "sstarlette.authentication.models.token_encoder_and_decoder"
    )
    # mock_generate_token = mocker.patch(
    #     "authentication_service.models.create_access_token"
    # )
    _mock_generate_token.return_value = (
        lambda *args, **kwargs: "access token",
        lambda *args, **kwargs: "",
    )
    return _mock_generate_token


@pytest.fixture
def signup_helper(client: httpx.Client):
    async def _signup_helper(json_params: dict, headers: dict = None):
        # with client as c:
        response = await client.post(
            "/signup",
            json={
                "full_name": "Fredo Alfredo",
                "email": "fredo@example.com",
                "signup_info": {"verification": "email"},
                **json_params,
            },
            headers=headers,
        )
        return response

    return _signup_helper


@pytest.mark.run_loop
async def test_signup_regular_user_with_password(
    mocker, create_future, signup_helper, mock_generate_token
):
    mock_email_verification = mocker.patch(
        "authentication_service.service_layer.utils.email_verification"
    )
    mock_email_verification.return_value = create_future(
        {"msg": "Email verification sent", "status": True}
    )
    create_verification_token = mocker.patch(
        "authentication_service.utils.verify_email_token"
    )
    # verification endpoint returns a response to activate the user account.
    async with models.User.database:
        await models.User.objects.delete()
        await user_count_assertion(0)
        response = await signup_helper({"password": "fredo101"})
        assert response.json() == {
            "status": True,
            "data": {"access_token": "access token"},
        }
        mock_email_verification.assert_called_once_with(
            "fredo@example.com", "access token"
        )
        await user_email_verification_assertion(False)


@pytest.mark.run_loop
async def test_signup_regular_user_with_google_skipping_verification(
    client: testclient.TestClient,
    mocker,
    create_future,
    signup_helper,
    mock_generate_token,
):
    provider_authorization = mocker.patch(
        "authentication_service.service_layer.utils.provider_verification"
    )
    signup_info = {
        "signup_info": {
            "provider": "google",
            "client_id": "google_client_id",
            "verify": False,
        }
    }
    signup_func = lambda: signup_helper(signup_info, {"G_Authorization": "GoogleTOKEN"})
    async with models.User.database:
        await models.User.objects.delete()
        # successful identity verification
        provider_authorization.return_value = create_future(True)
        assert await models.User.objects.count() == 0

        response = await signup_func()
        provider_authorization.assert_called_with(
            "google",
            {"email": "fredo@example.com", "full_name": "Fredo Alfredo"},
            access_token="GoogleTOKEN",
            client_id="google_client_id",
            verify=False,
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": True,
            "data": {"access_token": "access token"},
        }
        await user_email_verification_assertion(True)


@pytest.mark.run_loop
async def test_signup_regular_user_without_password(
    client: testclient.TestClient,
    mocker,
    create_future,
    signup_helper,
    mock_generate_token,
):
    provider_authorization = mocker.patch(
        "authentication_service.service_layer.utils.provider_verification"
    )
    signup_info = {
        "signup_info": {"provider": "google", "client_id": "google_client_id"}
    }
    async with models.User.database:
        await models.User.objects.delete()
        # missing auth header
        response = await signup_helper(signup_info)
        assert response.status_code == 400
        assert response.json() == {
            "status": False,
            "msg": "Missing Authorization header",
        }
        # failed identity verification
        provider_authorization.return_value = create_future(False)
        signup_func = lambda: signup_helper(
            signup_info, {"G_Authorization": "GoogleTOKEN"}
        )
        response = await signup_func()
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Error verifying identity"}
        # successful identity verification
        provider_authorization.return_value = create_future(True)
        assert await models.User.objects.count() == 0

        response = await signup_func()
        provider_authorization.assert_called_with(
            "google",
            {"email": "fredo@example.com", "full_name": "Fredo Alfredo"},
            access_token="GoogleTOKEN",
            client_id="google_client_id",
            verify=True,
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": True,
            "data": {"access_token": "access token"},
        }
        await user_email_verification_assertion(True)


@pytest.mark.run_loop
async def test_signup_admin(
    client: testclient.TestClient,
    mocker,
    create_future,
    signup_helper,
    mock_generate_token,
):
    admin_verification = mocker.patch(
        "authentication_service.service_layer.utils.provider_verification"
    )
    # deny admin access
    admin_verification.return_value = create_future(False)
    additional_info = {
        "password": "james-password",
        "signup_info": {"provider": "admin"},
    }
    async with models.User.database:
        await models.User.objects.delete()
        admin_func = lambda: signup_helper(
            additional_info, {"G_Authorization": "Admin101"}
        )
        response = await admin_func()
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Not Authorized"}
        # without admin header
        response = await signup_helper(additional_info)
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Not Authorized"}
        # valid admin creation
        admin_verification.return_value = create_future(True)
        response = await admin_func()
        assert response.status_code == 200
        assert response.json() == {
            "status": True,
            "data": {"access_token": "access token"},
        }
        # await user_count_assertion(1)
        assert await models.User.objects.count() == 1
        user = await models.User.objects.first()
        assert user.is_superuser
        assert user.is_staff


@pytest.mark.run_loop
async def test_signup_staff(
    client: testclient.TestClient,
    mocker,
    create_future,
    signup_helper,
    mock_generate_token,
):
    staff_verification = mocker.patch(
        "authentication_service.service_layer.utils.provider_verification"
    )
    # not authorized staff
    staff_info = {
        "password": "password101",
        "department": "Sales",
        "signup_info": {"provider": "staff"},
    }
    staff_verification.return_value = create_future(False)
    async with models.User.database:
        await models.User.objects.delete()
        staff_func = lambda: signup_helper(staff_info)
        response = await staff_func()
        assert response.status_code == 400
        assert response.json() == {
            "status": False,
            "msg": "Contact Admin for signup access",
        }
        # No department
        response = await signup_helper({**staff_info, "department": None})
        assert response.status_code == 400
        assert response.json() == {
            "status": False,
            "msg": "Department for staff missing",
        }
        # valid access
        staff_verification.return_value = create_future(True)
        response = await staff_func()
        assert response.json() == {
            "status": True,
            "data": {"access_token": "access token"},
        }
        assert response.status_code == 200

        user = await models.User.objects.first()
        assert not user.is_superuser
        assert user.is_staff
