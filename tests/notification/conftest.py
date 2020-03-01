import typing

import pytest

from sstarlette.notification.base import NotificationStarlette
from sstarlette.notification.service_layer import NotificationLayer


class TestNotificationLayer(NotificationLayer):
    pass


@pytest.fixture
def client_app():
    def _app(
        user_model, kls=NotificationStarlette, cls=SStarlette, as_app=False, **kwargs
    ) -> typing.Callable:
        app = kls(cls, user_model).init_app(**kwargs)
        if as_app:
            return app
        return httpx.AsyncClient(app=app, base_url="http://test_server")

    return _app


@pytest.fixture
def auth_client(client_app):
    return client_app(TestNotificationLayer(), enforce_auth=True)


@pytest.fixture
def client(client_app):
    return client_app(TestNotificationLayer())
