import asyncio
import json
import os

import databases
import httpx
import pytest
from alembic import command
from alembic.config import Config
from starlette.testclient import TestClient
from starlette.config import environ

environ["TESTING"] = "True"
environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL")
# environ["DATABASE_URL"] = "postgresql://staging:e_bots1991@dev.tuteria.com/staging_db"
environ["HOST_URL"] = "http://teserver.com"
environ["GOOGLE_PROJECT_ID"] = "project_id"
environ["NOTIFICATION_SERVICE"] = "http://notification-service"
environ["GOOGLE_STAFF_SHEET_URL"] = "http://staff-auth?true"
environ["GOOGLE_PRIVATE_KEY_ID"] = "private_key_id"
environ["GOOGLE_PRIVATE_KEY"] = "private_key"
environ["GOOGLE_CLIENT_EMAIL"] = "jane@example.com"
environ["GOOGLE_CLIENT_ID"] = "client_id"
environ["STAFF_ACCESS_CODE"] = "StaffAccess"


from authentication_service import settings, models
from authentication_service.models import init_tables
from authentication_service.views import app
from orm.test_utils import *

# from run import app


@pytest.fixture
def client():
    return httpx.Client(app=app, base_url="http://test_server")
    # return httpx.Client(app=app,base_url="http://test_server")
    # return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="session")
def metadata(database):
    metadata = init_tables(database)
    return metadata


@pytest.fixture(scope="session")
def database():
    return databases.Database(str(settings.DATABASE_URL))


@pytest.fixture
def engine():
    return sqlalchemy.create_engine(str(settings.DATABASE_URL))


@pytest.fixture(autouse=True, scope="session")
def create_test_database(metadata, monkeysession, clear_db):
    engine = sqlalchemy.create_engine(str(settings.DATABASE_URL))
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


@pytest.fixture
def create_redis(closable, loop):
    """Wrapper around aioredis.create_redis."""

    async def f(*args, **kw):
        kw.setdefault("loop", loop)
        redis = await aioredis.create_redis(
            settings.CACHE_URL, *args, encoding="utf-8", **kw
        )
        closable(redis)
        return redis

    return f


@pytest.fixture(scope="session")
def clear_db():
    """Destroy tables after creation"""

    async def _clear_db(*args, **kw):
        # kw.setdefault("loop", loop)
        async with models.User.database:
            await models.User.objects.delete()
            await models.Role.objects.delete()
            await models.Permission.objects.delete()

    return _clear_db

