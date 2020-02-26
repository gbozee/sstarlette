import asyncio
import json
import os
import typing

import databases
import httpx
import pytest
import sqlalchemy
from orm import Base, utils
from pydantic import EmailStr
from starlette.authentication import BaseUser, SimpleUser
from starlette.config import environ
from starlette.testclient import TestClient

from sstarlette.base import ServiceResult
from sstarlette.sql import SStarlette, VerifiedUser

environ["TESTING"] = "True"
DATABASE_URL = "sqlite:///app.db"


class User(Base, BaseUser):
    full_name: str
    email: EmailStr
    is_active: bool = True

    class Config:
        table_name = "user"
        table_config = {
            "id": {"primary_key": True, "index": True, "unique": True},
            "full_name": {"index": True},
            "email": {"index": True, "unique": True},
        }


class AuthorizedUser(typing.NamedTuple):
    auth_roles: typing.List[str]
    user: User


def init_tables(database, replica_database=None):
    metadata = utils.init_tables(Base, database, replica_database=replica_database)
    return metadata


async def sample_service(**kwargs) -> ServiceResult:
    query_params = kwargs.pop("query_params")
    return ServiceResult(data=dict(query_params))


async def with_error(**kwargs):
    return ServiceResult(errors={"msg": "Bad info"})


async def bg(**kwargs):
    return await User.objects.create(**kwargs)


async def with_background_task(post_data, **kwargs):
    return ServiceResult(data={"result": "processing"}, task=[[bg, post_data]])


async def with_redirect(**kwargs) -> ServiceResult:
    return ServiceResult(data={"name": "http://www.google.com"})


async def verify_access_token(bearer_token, **kwargs) -> AuthorizedUser:
    user = await User.objects.get(email=bearer_token)
    if not user:
        raise ValueError
    return AuthorizedUser(auth_roles=["authenticated"], user=user)


async def protected_route(user=None, **kwargs):
    return ServiceResult(data=user.full_name)


service_layer = {
    "/service": {"func": sample_service, "methods": ["GET"]},
    "/with-error": {"func": with_error, "methods": ["GET"]},
    "/with-background": {"func": with_background_task, "methods": ["POST"]},
    "/with-redirect": {
        "func": with_redirect,
        "methods": ["GET"],
        "redirect": True,
        "redirect_key": "name",
    },
    "/protected": {
        "func": protected_route,
        "auth": "authenticated",
        "methods": ["GET"],
    },
    "/skip-db": {"func": with_redirect, "methods": ["GET"], "no_db": True},
}


def default_callback(kls, verified_user: AuthorizedUser):
    return kls(verified_user.auth_roles), verified_user.user


@pytest.fixture
def db_model():
    return User


@pytest.fixture
def app(client_app):
    def _app(as_app=True, **kwargs):
        return client_app(
            kls=SStarlette,
            database_url=DATABASE_URL,
            model_initializer=init_tables,
            service_layer=service_layer,
            as_app=as_app,
            auth_result_callback=default_callback,
            auth_token_verify_user_callback=verify_access_token,
            **kwargs
        )

    return _app


@pytest.fixture
def client(app):
    return app(as_app=False)
    # return httpx.Client(app=app,base_url="http://test_server")
    # return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="session")
def metadata(database):
    metadata = init_tables(database)
    return metadata


@pytest.fixture(scope="session")
def database():
    return databases.Database(DATABASE_URL)


@pytest.fixture
def engine():
    return sqlalchemy.create_engine(DATABASE_URL)


@pytest.fixture(autouse=True, scope="session")
def create_test_database(metadata, monkeysession):
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.create_all(engine)
    # config = Config("alembic.ini")   # Run the migrations.
    # command.upgrade(config, "head")
    yield
    # command.downgrade(config, "head")                  # Run the tests.
    metadata.drop_all(engine)


@pytest.fixture(scope="session")
def monkeysession(request):
    from _pytest.monkeypatch import MonkeyPatch

    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture
def create_future():
    def _create_future(value):
        dd = asyncio.Future()
        dd.set_result(value)
        return dd

    return _create_future
