import typing

from starlette.applications import Starlette
from starlette.authentication import requires
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from sstarlette.db.base import DBAbstraction
from sstarlette.db.base import SResult as ServiceResult
from sstarlette.logging.base import MonitoringBase


class RouteType:
    def __init__(self, path: str, endpoint: typing.Callable, methods: typing.List[str]):
        self.path = path
        self.endpoint = endpoint
        self.methods = methods


class SStarlette(Starlette):
    def __init__(
        self,
        db_layer: DBAbstraction = None,
        monitoring_layer: MonitoringBase = None,
        service_layer: typing.Dict[str, typing.Any] = None,
        **kwargs,
    ):
        self.database = None
        self.db_layer = db_layer
        self.monitoring_layer = monitoring_layer
        if not self.db_layer:
            self.db_layer = DBAbstraction()
        if not self.monitoring_layer:
            self.monitoring_layer = MonitoringBase()
        self.is_serverless = kwargs.pop("serverless", False)
        routes = kwargs.pop("routes", [])
        additional_routes = self.monitoring_layer.build_routes(
            routes, is_serverless=self.is_serverless
        )
        if service_layer:
            additional_routes += self.monitoring_layer.build_routes(
                [self.build_view(key, **value) for key, value in service_layer.items()],
                is_serverless=self.is_serverless,
            )
        routes = additional_routes

        super().__init__(
            routes=routes, **kwargs,
        )

    def json_response(self, *args, **kwargs) -> Response:
        layer = self.db_layer
        return layer.json_response(*args, is_serverless=self.is_serverless, **kwargs)

    async def build_response(self, *args, **kwargs) -> Response:
        return await self.db_layer.build_response(
            *args, is_serverless=self.is_serverless, **kwargs
        )

    def build_view(
        self,
        path: str,
        func: typing.Callable,
        methods: typing.List[str] = ["POST"],
        auth: str = None,
        redirect: bool = False,
        redirect_key: str = None,
        skip: bool = False,
        **kwargs,
    ) -> RouteType:
        async def f(request: Request):
            post_data = None
            headers = request.headers
            user = None
            if skip:
                return await self.build_response(
                    func(request),
                    redirect_key=redirect_key,
                    redirect=redirect,
                    **kwargs,
                )
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
                    request=request,
                ),
                redirect_key=redirect_key,
                redirect=redirect,
                **kwargs,
            )

        function = f
        if auth:
            function = requires(auth)(f)
        return RouteType(path, function, methods)
