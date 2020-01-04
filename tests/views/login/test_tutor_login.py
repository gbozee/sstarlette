import httpx
import jwt
import pytest
from authentication_service import models, service_layer, settings


async def clean_db():
    await models.User.objects.delete()
    await models.Role.objects.delete()
    await models.Permission.objects.delete()
    assert await models.User.objects.count() == 0


async def create_sample_tutor():
    await service_layer.on_signup(
        {
            "full_name": "Danny Novak",
            "email": "danny@example.com",
            "gender": "M",
            "dob": "1991-12-16",  # year-month-day
            "password": "dannypassword",
            "signup_info": {"verification": None},
        },
        {},
    )
    assert await models.User.objects.count() == 1
    return await models.User.objects.get(email="danny@example.com")


@pytest.mark.asyncio
async def test_tutor_login_with_email_and_password(client: httpx.Client):
    async with models.User.database:
        await clean_db()
        await create_sample_tutor()
        response = await client.post(
            "/login", json={"email": "danny@example.com", "password": "dannypassword"}
        )
        assert response.status_code == 200
        data = response.json()
        token = data["data"]["access_token"]
        d_token = jwt.decode(token, verify=False)
        assert "danny@example.com" in d_token.values()
        # when password is wrong
        response = await client.post(
            "/login", json={"email": "danny@example.com", "password": "dannypassword1"}
        )
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Invalid credentials"}


@pytest.mark.asyncio
async def test_tutor_login_with_with_google(client: httpx.Client):
    async with models.User.database:
        await clean_db()
        await create_sample_tutor()
        response = await client.post(
            "/login",
            json={
                "email": "danny@example.com",
                "login_info": {
                    "provider": "google",
                    "verify": False,
                },  # just fetch user by email since no forced verification
            },
            headers={"g_authorization": "Bearer GoogleToken"},
        )
        assert response.status_code == 200
        data = response.json()
        token = data["data"]["access_token"]
        d_token = jwt.decode(token, verify=False)
        assert "danny@example.com" in d_token.values()
        # when email doesn't exist
        response = await client.post(
            "/login",
            json={
                "email": "danny2@example.com",
                "login_info": {
                    "provider": "google",
                    "verify": False,
                },  # just fetch user by email since no forced verification
            },
            headers={"g_authorization": "Bearer GoogleToken"},
        )
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Invalid credentials"}


@pytest.mark.asyncio
async def test_tutor_login_with_facebook(client: httpx.Client):
    async with models.User.database:
        await clean_db()
        await create_sample_tutor()
        response = await client.post(
            "/login",
            json={
                "email": "danny@example.com",
                "login_info": {
                    "provider": "facebook",
                    "verify": False,
                },  # just fetch user by email since no forced verification
            },
            headers={"g_authorization": "Bearer FacebookToken"},
        )
        assert response.status_code == 200
        data = response.json()
        token = data["data"]["access_token"]
        d_token = jwt.decode(token, verify=False)
        assert "danny@example.com" in d_token.values()
        # when email doesn't exist
        response = await client.post(
            "/login",
            json={
                "email": "danny2@example.com",
                "login_info": {
                    "provider": "facebook",
                    "verify": False,
                },  # just fetch user by email since no forced verification
            },
            headers={"g_authorization": "Bearer GoogleToken"},
        )
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Invalid credentials"}


@pytest.mark.asyncio
async def test_delete_users_for_test_scenario(client: httpx.Client):
    async with models.User.database:
        await clean_db()
        await create_sample_tutor()
        response = await client.post(
            f"/delete-user", json={"email": "danny@example.com"}
        )
        assert response.status_code == 200
        assert await models.User.objects.count() == 0
