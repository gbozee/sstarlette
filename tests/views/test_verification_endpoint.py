import httpx
import pytest
from starlette import testclient

from authentication_service import models, settings, utils
from shared import clear_db, create_user, user_email_verification_assertion


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
async def test_email_verification(
    client: testclient.TestClient,
    mocker,
    create_future,
    mock_response,
    create_redis,
    mock_generate_token,
):
    conn = await create_redis()
    mock_redis = mocker.patch("authentication_service.utils.redis_connection")
    mock_redis.return_value = create_future(conn)
    mock_module = mocker.patch("authentication_service.utils.httpx.Client")
    mock_client = mock_module.return_value
    mock_client.post.return_value = create_future(
        mock_response({"status": True}, overwrite=True)
    )
    async with models.User.database:
        # when token is passed
        await utils.email_verification("james@example.com", token="The user token")
        mock_client.post.assert_called_with(
            "http://notification-service",
            json={
                "email": "james@example.com",
                "callback_url": f"http://teserver.com/verify-email?email=james@example.com&token=The user token",
            },
        )
        # when token isn't passed, get temporary token from user.
        await clear_db()
        mock_generate_token("access-token")
        user = await create_user()
        await utils.email_verification(user.email)
        mock_client.post.assert_called_with(
            "http://notification-service",
            json={
                "email": user.email,
                "callback_url": (
                    f"http://teserver.com/verify-email?email={user.email}&token=access-token"
                ),
            },
        )
        # when custom callback_url is passed
        await utils.email_verification(
            "james@example.com", token="The user token", callback_url="http://user.com"
        )
        mock_client.post.assert_called_with(
            "http://notification-service",
            json={
                "email": "james@example.com",
                "callback_url": (
                    "http://teserver.com/verify-email?"
                    "email=james@example.com&token=The user token&callback_url=http://user.com"
                ),
            },
        )
        # when a 400 error occurs from
        mock_client.post.return_value = create_future(
            mock_response(
                {"status": False, "msg": "Invalid "}, status_code=400, overwrite=True
            )
        )

        with pytest.raises(httpx.HTTPError) as e:
            await utils.email_verification(
                "james@example.com",
                token="The user token",
                callback_url="http://user.com",
            )
            assert e["msg"] == "Invalid"


@pytest.mark.run_loop
async def test_auth_provider_verification(mocker):
    # test google verification
    mock_g = mocker.patch("authentication_service.utils.authorizer.google_verification")
    # invalid authorization
    mock_g.return_value = {"email": "johndoe@example.com"}
    result = await utils.provider_verification(
        "google", {"email": "same@example.com"}, "special_token", client_id="1234"
    )
    assert not result
    mock_g.assert_called_with("special_token", "1234")
    # when exception is raised
    mock_g.side_effect = ValueError("Thrown")
    result = await utils.provider_verification(
        "google", {"same@example.com"}, "special_token", client="1234"
    )
    assert not result
    # when valid
    mock_g.side_effect = None
    mock_g.return_value = {"email": "same@example.com"}
    result = await utils.provider_verification(
        "google", {"email": "same@example.com"}, "special_token", client="1234"
    )
    assert result
    # test staff verification
    mock_g = mocker.patch("authentication_service.utils.authorizer.staff_verification")
    mock_g.return_value = False
    result = await utils.provider_verification("staff", {"email": "sames@example.com"})
    assert not result
    mock_g.assert_called_with(
        "sames@example.com",
        role="staff",
        key_location="",
        file_url="http://staff-auth?true",
        config_obj={
            "project_id": "project_id",
            "private_key_id": "private_key_id",
            "private_key": "private_key",
            "client_email": "jane@example.com",
            "client_id": "client_id",
        },
    )
    # test admin verification
    mock_g.return_value = True
    result = await utils.provider_verification("admin", {"email": "jane@example.com"})
    assert result
    mock_g.assert_called_with(
        "jane@example.com",
        role="admin",
        key_location="",
        file_url="http://staff-auth?true",
        config_obj={
            "project_id": "project_id",
            "private_key_id": "private_key_id",
            "private_key": "private_key",
            "client_email": "jane@example.com",
            "client_id": "client_id",
        },
    )
