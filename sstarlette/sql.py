import typing

from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from sstarlette.base import RouteType
from sstarlette.with_middleware import SStarlette as BaseStarlette
from sstarlette.db.sql import SQLDataAbstraction
from sstarlette.logging.base import MonitoringBase


def on_auth_error(request: Request, exc: Exception):
    return JSONResponse({"status": False, "msg": str(exc)}, status_code=403)


async def not_authorized(request, exc):
    return JSONResponse(
        {"status": False, "msg": "Not Authorized"}, status_code=exc.status_code
    )


class VerifiedUser(typing.NamedTuple):
    auth_roles: typing.List[str]


def default_callback(kls, verified_user: VerifiedUser):
    return kls(verified_user.auth_roles), verified_user


class SStarlette(BaseStarlette):
    def __init__(
        self,
        database_url: str = None,
        sentry_dsn: str = None,
        replica_database_url=None,
        auth_token_verify_user_callback=None,
        auth_result_callback=default_callback,
        **kwargs,
    ):
        model_initializer = kwargs.pop("model_initializer", None)
        replica = replica_database_url
        if replica_database_url:
            replica = str(replica_database_url)
        db_layer = SQLDataAbstraction(
            database_url,
            replica_database_url=replica,
            model_initializer=model_initializer,
        )
        if sentry_dsn:
            from sstarlette.logging.sentry_patch import SentryMonitoring

            monitoring_layer = SentryMonitoring(sentry_dsn)
        else:
            monitoring_layer = MonitoringBase()
        self.redis = None

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
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            cors=True,
            auth_token_verify_user_callback=auth_token_verify_user_callback,
            on_auth_error=on_auth_error,
            auth_result_callback=auth_result_callback,
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
