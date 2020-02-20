import typing

import jwt
from sstarlette.sentry_patch import serverless_function
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
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route


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


class SStarlette(Starlette):
    def __init__(
        self,
        database_url: str = None,
        replica_database_url=None,
        sentry_dsn: str = None,
        auth_token_verify_user_callback=None,
        cors=True,
        service_layer: typing.Dict[str, typing.Any] = None,
        **kwargs
    ):
        self.database = None
        self.sentry_dsn = sentry_dsn
        if database_url:
            import databases

            self.database = databases.Database(database_url)
            self.replica_database = None
            if replica_database_url:
                self.replica_database = databases.Database(str(replica_database_url))
        self.is_serverless = kwargs.pop("serverless", False)
        self.model_initializer = kwargs.pop("model_initializer", None)
        additional_middlewares = kwargs.pop("middleware", []) or []
        middlewares = self.populate_middlewares(
            auth_token_verify_user_callback,
            cors=cors,
            debug=kwargs.get("debug") or False,
        )
        middlewares.extend(additional_middlewares)
        exception_handlers = kwargs.pop("exception_handlers", {})
        exception_handlers = {403: not_authorized, **exception_handlers}
        self.redis = None
        routes = kwargs.pop("routes", [])
        on_startup = kwargs.pop("on_startup", [])
        on_shutdown = kwargs.pop("on_shutdown", [])
        on_startup.append(self.startup)
        on_shutdown.append(self.shutdown)
        if service_layer:
            additional_routes = [
                self.build_view(key, **value) for key, value in service_layer.items()
            ]
            if self.is_serverless:
                additional_routes.extend(
                    [
                        Route(
                            x.path, serverless_function(x.endpoint), methods=x.methods
                        )
                        for x in routes
                    ]
                )
            routes = additional_routes
            # routes.extend(additional_routes)
        super().__init__(
            routes=routes,
            middleware=middlewares,
            exception_handlers=exception_handlers,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            **kwargs
        )

    def populate_middlewares(
        self, auth_token_verify_user_callback=None, cors=True, debug=False
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
            if self.sentry_dsn:
                from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

                middlewares.append(Middleware(SentryAsgiMiddleware))
                print("Adding Sentry middleware to application")
        return middlewares

    def initialize_sentry(self):
        import sentry_sdk
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        if self.sentry_dsn:
            sentry_sdk.init(
                dsn=self.sentry_dsn,
                send_default_pii=True,
                integrations=[SqlalchemyIntegration()],
            )

    async def connect_db(self) -> bool:
        started = False
        if self.database:
            if not self.database.is_connected:
                await self.database.connect()
                started = True
            if self.replica_database:
                if not self.replica_database.is_connected:
                    await self.replica_database.connect()
            if self.model_initializer:
                self.model_initializer(
                    self.database, replica_database=self.replica_database
                )
        return started

    async def disconnect_db(self):
        if self.database:
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
                    try:
                        dict_index = [type(o) for o in i].index(dict)
                        kwarg_props = i[dict_index]
                        args_props = i[0:dict_index]
                        tasks.add_task(*args_props, **kwarg_props)
                    except ValueError:
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

    def build_view(
        self,
        path: str,
        func: typing.Callable,
        methods: typing.List[str] = ["POST"],
        auth: str = None,
        redirect: bool = False,
        redirect_key: str = None,
        no_db: bool = False,
        skip: bool = False,
    ):
        async def f(request: Request):
            post_data = None
            headers = request.headers
            user = None
            if skip:
                return await func(request)
            if "POST" in methods:
                post_data = await request.json()
            if auth:
                user = request.user
            return await self.build_response(
                func(
                    post_data=post_data,
                    query_params=request.query_params,
                    headers=request.headers,
                    path_params=request.path_params,
                    user=user,
                ),
                redirect_key=redirect_key,
                redirect=redirect,
                no_db=no_db,
            )

        function = f
        if auth:
            function = requires(auth)(f)
        if self.is_serverless:
            function = serverless_function(function)
        return Route(path, function, methods=methods)

    async def startup(self):
        await self.connect_db()

    async def shutdown(self):
        await self.disconnect_db()
