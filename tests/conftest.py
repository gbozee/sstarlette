import httpx
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
import utils
from sstarlette.base import ServiceResult, SStarlette


async def home(request: Request):
    return JSONResponse({"home": True})


@pytest.fixture
def client_app():
    def _app(kls=SStarlette, as_app=False, **kwargs):
        app = kls(routes=[Route("/", endpoint=home, methods=["GET"])], **kwargs)
        if as_app:
            return app
        return httpx.AsyncClient(app=app, base_url="http://test_server")

    return _app
