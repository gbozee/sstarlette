import typing

import jwt
import pytest
import asyncpg
from datetime import datetime
from authentication_service import models
from authentication_service.models.utils import decode_access_token
from views.shared import clear_db


async def create_roles():
    roles = ["Admin", "Staff", "Client", "Tutor"]
    await models.Role.objects.bulk_create_or_insert(
        [models.Role(name=x) for x in roles]
    )
    return roles


async def create_permissions():
    permissions = [
        {"name": "edit account"},
        {"name": "teach group lessons"},
        {"name": "access entire site", "role": "Admin"},
    ]
    roles = await models.Role.objects.all()
    records = []
    for i in permissions:
        role = None
        role_list = [x for x in roles if i.get("role") == x.name]
        if len(role_list) > 0:
            role = role_list[0]
        records.append(models.Permission(name=i["name"], role=role))
    await models.Permission.objects.bulk_create_or_insert(records)


@pytest.mark.run_loop
async def test_user_model_with_roles_and_permission():
    async with models.User.database:
        await clear_db()
        await create_roles()
        await create_permissions()
        instance: models.User = await models.User.objects.create(
            full_name="Biola", email="james@example.com", roles=["Admin"]
        )
        assert instance.id
        # fetch the roles the user belongs to
        user_roles: typing.List[models.Role] = await instance.get_roles()
        assert len(user_roles) == 1
        assert user_roles[0].name == "Admin"
        # view the permissions of the user. should include permissions attached to roles.
        user_permissions = await instance.get_permissions()
        assert len(user_permissions) == 1
        assert user_permissions[0].name == "access entire site"
        # add additional permissions
        instance.additional_permissions.append("teach group lessons")
        await instance.save()
        assert instance.additional_permissions == ["teach group lessons"]
        user_permissions = await instance.get_permissions()
        assert len(user_permissions) == 2
        assert ["access entire site", "teach group lessons"] == sorted(
            [x.name for x in user_permissions]
        )


@pytest.mark.run_loop
async def test_password_generation():
    async with models.User.database:
        await clear_db()
        user: models.User = await models.User.objects.create(
            full_name="Alfredo Cuomo", email="fredo@example.com"
        )
        user.set_password("password")
        await user.save()
        assert user.password != "password"
        assert user.check_password("password")


@pytest.mark.run_loop
async def test_access_token_generation(mocker):
    async with models.User.database:
        await clear_db()
        await create_roles()
        await create_permissions()
        user: models.User = await models.User.objects.create(
            full_name="Biola", email="james22@example.com", roles=["Admin"]
        )
        token = await user.generate_access_token(with_permissions=False)
        # verify the token
        decoded_token = decode_access_token(token)
        assert decoded_token["full_name"] == "Biola"
        assert decoded_token["email"] == "james22@example.com"

        # create token for specific role
        token = await user.generate_access_token(with_permissions=True)
        with pytest.raises(jwt.exceptions.InvalidAudienceError):
            decode_access_token(token)
        decoded_token = decode_access_token(token, audience="access entire site")
        assert decoded_token["aud"] == ["access entire site"]
        # test expired token
        mock_now = mocker.patch("sstarlette.authentication.helpers.current_time")
        mock_now.return_value = datetime(2019, 8, 15, 5, 4, 3)
        token = await user.generate_access_token(
            expires=60 * 60, with_permissions=False
        )
        mock_now.return_value = datetime.now()
        assert models.User.is_expired_token(token)


@pytest.mark.run_loop
async def test_prevent_duplicate_emails():
    async with models.User.database:
        await clear_db()
        await create_roles()
        await create_permissions()
        user: models.User = await models.User.objects.create(
            full_name="Biola", email="james7@example.com", roles=["Admin"]
        )
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            user2: models.User = await models.User.objects.create(
                full_name="Biola", email="james7@example.com", roles=["Admin"]
            )


@pytest.mark.run_loop
async def test_create_unverified_user():
    async with models.User.database:
        await clear_db()
        await create_roles()
        await create_permissions()
        # assert missing field error
        user: models.User = await models.User.objects.create(
            full_name="Biola", email="james3@example.com", roles=["Admin"]
        )
        error, instance, _ = await models.User.create_unverified_user(
            **{
                "full_name": "John doe",
                "password": "password",
                # "email": "fredo@example.com",
            }
        )
        assert error == {"email": ["value_error.missing"]}
        assert not instance
        # assert duplicate email
        error, instance, _ = await models.User.create_unverified_user(
            full_name="Biola", email="james3@example.com"
        )
        assert error == {"email": ["value_error.duplicate"]}
        # valid call
        error, instance, _ = await models.User.create_unverified_user(
            full_name="Shope", email="fredo2@example.com", password="john doe"
        )
        assert not error
        assert not instance.verified
        assert instance.check_password("john doe")


@pytest.mark.run_loop
async def test_downgrade_token_access_from_staff_or_admin():
    async with models.User.database:
        await clear_db()
        await create_roles()
        await create_permissions()
        # assert missing field error
        user: models.User = await models.User.objects.create(
            full_name="Biola", email="james2@example.com", roles=["Admin"]
        )
        assert user.is_superuser
        user_token = await user.create_user_token()
        decoded_value = decode_access_token(user_token)
        assert not decoded_value.get("aud")

