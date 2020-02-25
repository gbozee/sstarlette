import typing

from starlette.middleware import Middleware
from starlette.routing import Route


class MonitoringBase:
    def initialize(self, *args, **kwargs):
        pass

    def build_routes(self, routes: typing.List[Route], **kwargs) -> typing.List[Route]:
        return [Route(x.path, x.endpoint, methods=x.methods) for x in routes]

    def middleware(self) -> typing.Optional[Middleware]:
        return None
