import typing

import databases
import jwt
from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    requires,
)
from starlette.background import BackgroundTasks
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse


class SResult:
    def __init__(
        self,
        errors: dict = None,
        data: dict = None,
        task: typing.List[typing.Any] = None,
    ):
        self.errors = errors
        self.data = data
        self.task = task


def on_auth_error(request: Request, exc: Exception):
    return JSONResponse({"status": False, "msg": str(exc)}, status_code=403)


def build_token_backend(verified_user_callback):
    class TokenBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
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


class SStarlette(Starlette):
    def __init__(self, database_url: str, *args, replica_database_url=None, **kwargs):
        self.database = databases.Database(database_url)
        self.replica_database = None
        if replica_database_url:
            self.replica_database = databases.Database(str(replica_database_url))
        self.is_serverless = kwargs.pop("serverless", False)
        self.model_initializer = kwargs.pop("model_initializer", None)
        self.redis = None
        super().__init__(*args, **kwargs)

    def populate_middlewares(
        self,
        auth_token_verify_user_callback=None,
        cors=True,
        sentry_dsn=None,
        debug=False,
    ) -> typing.List[Middleware]:
        middlewares = []
        if auth_token_verify_user_callback:
            token_class = build_token_backend(auth_token_verify_user_callback)
            middlewares.append(
                Middleware(
                    AuthenticationMiddleware,
                    backend=token_class(),
                    on_error=on_auth_error,
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
            if sentry_dsn:
                import sentry_sdk
                from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
                from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

                sentry_sdk.init(
                    dsn=sentry_dsn,
                    send_default_pii=True,
                    integrations=[SqlalchemyIntegration()],
                )
                middlewares.append(Middleware(SentryAsgiMiddleware))
                print("Adding Sentry middleware to application")
        return middlewares

    async def connect_db(self):
        started = False
        if not self.database.is_connected:
            await self.database.connect()
            started = True
        if self.replica_database:
            if not self.replica_database.is_connected:
                await self.replica_database.connect()
        if self.model_initializer:
            model_initializer(self.database, replica_database=self.replica_database)
        return started

    async def disconnect_db(self):
        if self.database.is_connected:
            await self.database.disconnect()
        if self.replica_database:
            if self.replica_database.is_connected:
                await self.replica_database.disconnect()

    def json_response(
        self,
        data,
        status_code: int = 200,
        tasks: BackgroundTasks = None,
        no_db=False,
        redirect=False,
    ) -> typing.Union[JSONResponse, RedirectResponse]:
        if tasks:
            if self.is_serverless and not no_db:
                tasks.add_task(self.disconnect_db)
            if self.redis:
                self.redis.close()
                tasks.add_task(self.redis.wait_closed)
        if redirect:
            return RedirectResponse(url=data, status_code=status_code)
        return JSONResponse(data, status_code=status_code, background=tasks)

    async def build_response(
        self,
        coroutine: typing.Awaitable,
        status_code: int = 400,
        no_db=False,
        redirect=False,
        redirect_key=None,
    ) -> typing.Union[JSONResponse, RedirectResponse]:
        if self.is_serverless and not no_db:
            await self.connect_db()
        result: SResult = await coroutine
        tasks = BackgroundTasks()
        if result.errors:
            return self.json_response(
                {"status": False, **result.errors},
                status_code=400,
                tasks=tasks,
                no_db=no_db,
            )
        if result.task:
            for i in result.task:
                if type(i) in [list, tuple]:
                    tasks.add_task(*i)
                else:
                    tasks.add_task(i)
        if redirect and redirect_key and result.data:
            redirect_url = result.data.get(redirect_key)
            return self.json_response(redirect_url, redirect=True, status_code=301)
        _result: typing.Dict[str, typing.Any] = {"status": True}
        if result.data:
            _result.update(data=result.data)
        return self.json_response(_result, tasks=tasks, no_db=no_db)
