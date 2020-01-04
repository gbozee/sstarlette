import httpx
import jwt
import pytest
from authentication_service import models, settings


async def clean_db():
    await models.User.objects.delete()
    await models.Role.objects.delete()
    await models.Permission.objects.delete()
    assert await models.User.objects.count() == 0


@pytest.mark.asyncio
async def test_tutor_signup_with_email(client: httpx.Client):
    signup_func = lambda: client.post(
        "/signup",
        json={
            "full_name": "Danny::Novak",
            "email": "danny@example.com",
            "gender": "M",
            "dob": "1991-12-16",  # year-month-day
            "password": "dannypassword",
            # sent in addition to signup info to skip email verification.
            "signup_info": {"verification": None},
        },
    )
    async with models.User.database:
        await clean_db()
        response = await signup_func()
        assert response.status_code == 200
        result: dict = response.json()
        access_token = result["data"]["access_token"]
        # decode jwt token
        user_data = jwt.decode(access_token, verify=False)
        user_info = {
            "email": "danny@example.com",
            "gender": "M",
            "full_name": "Danny::Novak",
            "first_name": "Danny",
            "birthday": "1991-12-16",
        }
        for key in user_info.keys():
            assert user_data[key] == user_info[key]
        record = await models.User.objects.get(email=user_data["email"])
        assert record.email == "danny@example.com"
        assert record.gender.value == "M"
        assert not record.email_verified
        # second attempt to signup should result in an error.
        response = await signup_func()
        assert response.status_code == 400
        assert response.json() == {
            "status": False,
            "errors": {"email": ["value_error.duplicate"]},
        }


@pytest.mark.asyncio
async def test_tutor_signup_with_google(client: httpx.Client):
    async with models.User.database:
        await clean_db()
        response = await client.post(
            "/signup",
            json={
                "full_name": "Danny::Novak",
                "email": "danny@example.com",
                "gender": "M",
                "dob": "1991-12-16",  # year-month-day
                "password": "dannypassword",
                # sent in addition to signup info to skip email verification.
                "signup_info": {
                    "verification": None,
                    "provider": "google",
                    "verify": False,
                },
            },
            headers={"g_authorization": "Bearer GoogleToken"},
        )
        assert response.status_code == 200
        result: dict = response.json()
        access_token = result["data"]["access_token"]
        # decode jwt token
        user_data = jwt.decode(access_token, verify=False)
        user_info = {
            "email": "danny@example.com",
            "gender": "M",
            "full_name": "Danny::Novak",
            "first_name": "Danny",
            "birthday": "1991-12-16",
        }
        for key in user_info.keys():
            assert user_data[key] == user_info[key]
        record = await models.User.objects.get(email=user_data["email"])
        assert record.email == "danny@example.com"
        assert record.gender.value == "M"
        assert record.email_verified  # google login.
        assert record.signup_info["provider"] == "google"


@pytest.mark.asyncio
async def test_tutor_signup_with_facebook(client: httpx.Client):
    async with models.User.database:
        await clean_db()
        response = await client.post(
            "/signup",
            json={
                "full_name": "Danny::Novak",
                "email": "danny@example.com",
                "gender": "M",
                "dob": "1991-12-16",  # year-month-day
                "password": "dannypassword",
                # sent in addition to signup info to skip email verification.
                "signup_info": {
                    "verification": None,
                    "provider": "facebook",
                    "verify": False,
                    "role": "tutor_applicant",
                },
            },
            headers={"g_authorization": "Bearer FacebookLongLivedToken"},
        )
        assert response.status_code == 200
        result: dict = response.json()
        access_token = result["data"]["access_token"]
        # decode jwt token
        user_data = jwt.decode(access_token, verify=False)
        user_info = {
            "email": "danny@example.com",
            "gender": "M",
            "full_name": "Danny::Novak",
            "first_name": "Danny",
            "birthday": "1991-12-16",
            "role": "tutor_applicant",
        }
        for key in user_info.keys():
            assert user_data[key] == user_info[key]
        record = await models.User.objects.get(email=user_data["email"])
        assert record.email == "danny@example.com"
        assert record.full_name == 'Danny::Novak'
        assert record.gender.value == "M"
        assert not record.email_verified  # google login.
        assert record.signup_info["provider"] == "facebook"

