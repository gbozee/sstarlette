import httpx
import pytest
from sstarlette.with_middleware import SStarlette

from sstarlette.authentication import AuthenticationStarlette


@pytest.fixture
def client_app():
    def _app(
        user_model, kls=AuthenticationStarlette, cls=SStarlette, as_app=False, **kwargs
    ):
        app = kls(cls, user_model).init_app(**kwargs)
        if as_app:
            return app
        return httpx.AsyncClient(app=app, base_url="http://test_server")

    return _app
