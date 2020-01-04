from authentication_service import models


async def user_email_verification_assertion(value):
    user = await models.User.objects.first()
    assert user.email_verified == value


async def db_assertion(coroutine):
    async with models.User.database:
        await coroutine


async def create_user(role="User", email="fredo@example.com", **kwargs):
    password = kwargs.pop("password", None)
    user_instance = await models.User.objects.create(
        full_name="Alfredo John", roles=[role], email=email, **kwargs
    )
    if password:
        user_instance.set_password(password)
        await user_instance.save()
    return user_instance


async def clear_db():

    await models.User.objects.delete()
    await models.Role.objects.delete()
    await models.Permission.objects.delete()


async def create_roles_and_permissions():
    roles = ["Admin", "Staff", "User"]
    await models.Role.objects.bulk_create_or_insert(
        [{"name": x} for x in roles], is_model=False
    )
    permissions = [
        {"name": "edit account", "role": ["Staff", "Admin"]},
        {"name": "teach group lessons", "role": ["User"]},
        {"name": "access entire site", "role": ["Admin"]},
    ]
    roles = await models.Role.objects.all()
    records = []
    for i in permissions:
        role = None
        role_list = [x for x in roles if x.name in i["role"]]
        for j in role_list:
            records.append(dict(name=i["name"], role_id=j.id))
    await models.Permission.objects.bulk_create_or_insert(records, is_model=False)
