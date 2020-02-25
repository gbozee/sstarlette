import httpx
import pytest
from starlette.testclient import TestClient
from orm import Base


@pytest.mark.asyncio
async def test_db_creation(db_model: Base, mocker):
    async with db_model.database:
        await db_model.objects.delete()
        assert await db_model.objects.count() == 0
        user = await db_model.objects.create(
            full_name="Jonny devito", email="jonny@example.com"
        )
        assert user.full_name == "Jonny devito"
        assert await db_model.objects.count() == 1


def test_default_route(db_model, app, mocker):
    app_instance = app()
    spy = mocker.spy(app_instance.db_layer, "connect")
    spy2 = mocker.spy(app_instance.db_layer, "disconnect")
    assert not spy.called
    assert not spy2.called
    with TestClient(app_instance) as client:
        assert spy.called
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"home": True}

    assert spy2.called


def test_serverless_call(app, mocker):
    app_instance = app(serverless=True)
    spy = mocker.spy(app_instance.db_layer, "connect")
    spy2 = mocker.spy(app_instance.db_layer, "disconnect")
    with TestClient(app_instance) as client:
        assert not spy.called
        assert not spy2.called
        response = client.get("/with-error")
        assert response.status_code == 400
        assert response.json() == {"status": False, "msg": "Bad info"}
    assert spy.called
    assert spy2.called
