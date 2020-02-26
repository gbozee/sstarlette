import typing

import jwt
from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from sstarlette.base import SStarlette as BaseStarlette
from sstarlette.db.base import DBAbstraction
from sstarlette.logging.base import MonitoringBase


def default_callback(kls, user):
    return kls(user), user


def build_token_backend(
    verified_user_callback,
    result_callback: typing.Callable = default_callback,
    auth_error_msg="Invalid token",
):
    class TokenBackend(AuthenticationBackend):
        async def authenticate(self, request: HTTPConnection):
            if "Authorization" not in request.headers:
                return

            auth = request.headers["Authorization"]
            bearer_token = auth.replace("Bearer", "").strip()
            try:
                verified_user = await verified_user_callback(bearer_token)
            except (jwt.exceptions.DecodeError, ValueError, KeyError) as e:
                raise AuthenticationError(auth_error_msg)
            else:
                return result_callback(AuthCredentials, verified_user)
                # AuthCredentials(verified_user.auth_roles), verified_user

    return TokenBackend


def populate_middlewares(
    auth_token_verify_user_callback=None,
    cors=True,
    debug=False,
    monitoring_middleware: typing.Optional[Middleware] = None,
    auth_result_callback=default_callback,
    auth_error_msg="Invalid token",
    on_auth_error=None,
) -> typing.List[Middleware]:
    middlewares = []
    if auth_token_verify_user_callback:
        token_class = build_token_backend(
            auth_token_verify_user_callback,
            result_callback=auth_result_callback,
            auth_error_msg=auth_error_msg,
        )
        middlewares.append(
            Middleware(
                AuthenticationMiddleware, backend=token_class(), on_error=on_auth_error,
            )
        )
    if cors:
        middlewares.append(
            Middleware(
                CORSMiddleware,
                allow_methods=["*"],
                allow_origins=["*"],
                allow_headers=["*"],
            )
        )
    if not debug:
        if monitoring_middleware:
            middlewares.append(monitoring_middleware)
            print("Adding Sentry middleware to application")
    return middlewares


class SStarlette(BaseStarlette):
    def __init__(
        self,
        db_layer: DBAbstraction = None,
        monitoring_layer: MonitoringBase = None,
        auth_token_verify_user_callback=None,
        cors=True,
        auth_result_callback=default_callback,
        on_auth_error=None,
        auth_error_msg="Invalid token",
        **kwargs,
    ):
        additional_middlewares = kwargs.pop("middleware", []) or []
        m_ware = monitoring_layer
        if not m_ware:
            m_ware = MonitoringBase()
        middlewares = populate_middlewares(
            auth_token_verify_user_callback,
            cors=cors,
            debug=kwargs.get("debug") or False,
            monitoring_middleware=m_ware.middleware(),
            on_auth_error=on_auth_error,
            auth_result_callback=auth_result_callback,
            auth_error_msg=auth_error_msg,
        )
        middlewares.extend(additional_middlewares)
        super().__init__(
            db_layer, monitoring_layer, middleware=middlewares, **kwargs,
        )

