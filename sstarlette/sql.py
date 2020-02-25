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

from sstarlette.base import RouteType
from sstarlette.base import SStarlette as BaseStarlette
from sstarlette.db.sql import SQLDataAbstraction
from sstarlette.logging.base import MonitoringBase


def on_auth_error(request: Request, exc: Exception):
    return JSONResponse({"status": False, "msg": str(exc)}, status_code=403)


async def not_authorized(request, exc):
    return JSONResponse(
        {"status": False, "msg": "Not Authorized"}, status_code=exc.status_code
    )


def build_token_backend(verified_user_callback):
    class TokenBackend(AuthenticationBackend):
        async def authenticate(self, request: HTTPConnection):
            if "Authorization" not in request.headers:
                return

            auth = request.headers["Authorization"]
            bearer_token = auth.replace("Bearer", "").strip()
            try:
                verified_user = await verified_user_callback(bearer_token)
            except (jwt.exceptions.DecodeError, ValueError, KeyError) as e:
                raise AuthenticationError("Invalid token")
            else:
                return AuthCredentials(verified_user.auth_roles), verified_user

    return TokenBackend


def populate_middlewares(
    auth_token_verify_user_callback=None,
    cors=True,
    debug=False,
    monitoring_middleware: typing.Optional[Middleware] = None,
) -> typing.List[Middleware]:
    middlewares = []
    if auth_token_verify_user_callback:
        token_class = build_token_backend(auth_token_verify_user_callback)
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
        database_url: str = None,
        sentry_dsn: str = None,
        replica_database_url=None,
        auth_token_verify_user_callback=None,
        cors=True,
        **kwargs,
    ):
        model_initializer = kwargs.pop("model_initializer", None)

        db_layer = SQLDataAbstraction(
            database_url,
            replica_database_url=replica_database_url,
            model_initializer=model_initializer,
        )
        if sentry_dsn:
            from sstarlette.logging.sentry_patch import SentryMonitoring

            monitoring_layer = SentryMonitoring(sentry_dsn)
        else:
            monitoring_layer = MonitoringBase()
        self.redis = None

        additional_middlewares = kwargs.pop("middleware", []) or []
        middlewares = populate_middlewares(
            auth_token_verify_user_callback,
            cors=cors,
            debug=kwargs.get("debug") or False,
            monitoring_middleware=monitoring_layer.middleware(),
        )
        middlewares.extend(additional_middlewares)
        exception_handlers = kwargs.pop("exception_handlers", {})
        exception_handlers = {403: not_authorized, **exception_handlers}
        on_startup = kwargs.pop("on_startup", [])
        on_shutdown = kwargs.pop("on_shutdown", [])
        self.is_serverless = kwargs.get("serverless", False)
        on_startup.append(self.startup)
        on_shutdown.append(self.shutdown)
        super().__init__(
            db_layer,
            monitoring_layer,
            exception_handlers=exception_handlers,
            middleware=middlewares,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            **kwargs,
        )

    def initialize_sentry(self):
        self.monitoring_layer.initialize(self.db_layer)

    def json_response(self, *args, **kwargs):
        tasks = kwargs.pop("tasks", None)
        if tasks:
            if self.redis:
                tasks.add_task(self.redis.wait_closed)
        return self.db_layer.json_response(
            *args, is_serverless=self.is_serverless, tasks=tasks, **kwargs
        )

    def build_view(self, *args, no_db: bool = False, **kwargs):
        return super().build_view(*args, no_db=no_db, **kwargs)

    async def startup(self):
        if not self.is_serverless:
            await self.db_layer.connect()

    async def shutdown(self):
        if not self.is_serverless:
            await self.db_layer.disconnect()
