import asyncio
import json
import os

import httpx
import pytest
from starlette.config import environ
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
import utils
from sstarlette.base import ServiceResult, SStarlette


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
            data={"result": "processing"}, task=[[utils.mock_func, 22, dict(age=33)]]
        )
    return ServiceResult(data={"result": "processing"}, task=[[utils.mock_func, 2]])


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
def client(client_app):
    return client_app(service_layer=service_layer)
