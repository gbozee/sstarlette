import asyncio
import json
import os

import httpx
import pytest
from starlette.authentication import SimpleUser
from starlette.config import environ
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import utils
from sstarlette.base import ServiceResult
from sstarlette.with_middleware import SStarlette


class CustomType(ServiceResult):
    def as_dict(self, status_code, tasks=None):
        if self.errors:
            result = self.errors
        else:
            result = {}
            if self.data:
                result = self.data
        return dict(data=result, status_code=status_code, tasks=tasks)


async def sample_service(**kwargs) -> ServiceResult:
    query_params = kwargs.pop("query_params")
    return ServiceResult(data=dict(query_params))


async def with_error(**kwargs):
    return CustomType(errors={"msg": "Bad info"})


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


async def protected_route(user=None, **kwargs):
    return ServiceResult(data=user.username)


async def verify_access_token(bearer_token, **kwargs):
    if "Not Authorized".lower() in bearer_token.lower():
        raise ValueError
    return {"name": "Shola", "roles": ["authenticated", "admin"]}


def auth_result_callback(kls, verified_user):
    return kls(verified_user["roles"]), SimpleUser(verified_user)


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
    "/protected": {
        "func": protected_route,
        "auth": "authenticated",
        "methods": ["GET"],
    },
}


@pytest.fixture
def client(client_app):
    return client_app(
        kls=SStarlette,
        service_layer=service_layer,
        auth_token_verify_user_callback=verify_access_token,
        auth_result_callback=auth_result_callback,
        auth_error_msg="Not Authorized",
    )
