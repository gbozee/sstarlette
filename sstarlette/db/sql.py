import typing

import databases
from starlette.background import BackgroundTasks

from .base import DBAbstraction


class SQLDataAbstraction(DBAbstraction):
    def __init__(
        self, url, replica_database_url=None, model_initializer: typing.Callable = None
    ):
        self.database = databases.Database(url)
        self.replica_database = None
        if replica_database_url:
            self.replica_database = databases.Database(replica_database_url)
        self.model_initializer = model_initializer

    async def connect(self):
        started = False
        if not self.database.is_connected:
            await self.database.connect()
            self.started = True
        if self.replica_database:
            if not self.replica_database.is_connected:
                await self.replica_database.connect()
        if self.model_initializer:
            self.model_initializer(
                self.database, replica_database=self.replica_database
            )
        return started

    async def disconnect(self):
        if self.database.is_connected:
            await self.database.disconnect()
        if self.replica_database:
            if self.database.is_connected:
                await self.replica_database.disconnect()

    def track(self, sentry_dsn):
        import sentry_sdk
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            send_default_pii=True,
            integrations=[SqlalchemyIntegration()],
        )

    def json_response(
        self,
        data,
        status_code: int = 200,
        tasks: BackgroundTasks = None,
        no_db=False,
        is_serverless=False,
        redirect=False,
        **kwargs
    ):
        if tasks:
            if is_serverless and not no_db:
                tasks.add_task(self.disconnect)
        return super().json_response(
            data, status_code=status_code, tasks=tasks, redirect=redirect
        )

    async def build_response(
        self,
        coroutine: typing.Awaitable,
        status_code: int = 400,
        no_db=False,
        is_serverless=False,
        redirect=False,
        redirect_key=None,
        **kwargs
    ):
        if is_serverless and not no_db:
            await self.connect()
        return await super().build_response(
            coroutine,
            status_code=status_code,
            redirect=redirect,
            redirect_key=redirect_key,
            is_serverless=is_serverless,
            no_db=no_db,
        )
