import asyncio
import json
import os

import databases
import httpx
import pytest
import sqlalchemy
from orm import Base, utils
from pydantic import EmailStr
from starlette.config import environ
from starlette.testclient import TestClient

from sstarlette.base import ServiceResult
from sstarlette.sql import SStarlette

environ["TESTING"] = "True"
# environ["DATABASE_URL"] = "postgresql://staging:e_bots1991@dev.tuteria.com/staging_db"
DATABASE_URL = "sqlite:///app.db"


class User(Base):
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


def init_tables(database, replica_database=None):
    metadata = utils.init_tables(Base, database, replica_database=replica_database)
    return metadata


async def sample_service(**kwargs) -> ServiceResult:
    query_params = kwargs.pop("query_params")
    return ServiceResult(data=dict(query_params))


async def with_error(**kwargs):
    return ServiceResult(errors={"msg": "Bad info"})


async def with_background_task(**kwargs):
    query_params = kwargs.get("query_params")
    keyword = query_params.get("keyword")
    if keyword:
        return ServiceResult(
            data={"result": "processing"}, task=[[mock_func, 22, dict(age=33)]]
        )
    return ServiceResult(data={"result": "processing"}, task=[[mock_func, 2]])


async def with_redirect(**kwargs) -> ServiceResult:
    return ServiceResult(data={"name": "http://www.google.com"})


service_layer = {
    "/service": {"func": sample_service, "methods": ["GET"]},
    "/with-error": {"func": with_error, "methods": ["GET"]},
    "/with-background": {"func": with_background_task, "methods": ["GET"]},
    "/with-redirect": {
        "func": with_redirect,
        "methods": ["GET"],
        "redirect": True,
        "redirect_key": "name",
    },
}


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
            **kwargs
        )

    return _app


@pytest.fixture
def client(app):
    return app(
        as_app=False,
        kls=SStarlette,
        database_url=DATABASE_URL,
        model_initializer=init_tables,
    )
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
